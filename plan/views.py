import os
import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Plans

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

from drf_spectacular.utils import extend_schema
from .serializers import PlanSerializer

class PlanListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        plans = Plans.objects.all().values(
            'id', 'name', 'plantype', 'price', 'questions_per_month', 'stripe_price_id', 'billing_cycle', 'badge', 'is_active', 'features'
        )
        return Response(list(plans), status=status.HTTP_200_OK)


class PlanDetailUpdateView(APIView):
    permission_classes = [AllowAny] # Use IsAdminUser in production

    def get(self, request, pk, *args, **kwargs):
        try:
            plan = Plans.objects.get(pk=pk)
            data = {
                'id': plan.id,
                'name': plan.name,
                'plantype': plan.plantype,
                'price': plan.price,
                'questions_per_month': plan.questions_per_month,
                'stripe_price_id': plan.stripe_price_id,
                'billing_cycle': plan.billing_cycle,
                'badge': plan.badge,
                'is_active': plan.is_active,
                'features': plan.features
            }
            return Response(data, status=status.HTTP_200_OK)
        except Plans.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(request=PlanSerializer, responses=PlanSerializer)
    def patch(self, request, pk, *args, **kwargs):
        try:
            plan = Plans.objects.get(pk=pk)
            
            data = request.data
            price_changed = False
            
            if 'name' in data:
                plan.name = data['name']
            if 'plantype' in data:
                plan.plantype = data['plantype']
            if 'price' in data:
                new_price = data['price']
                if float(new_price) != float(plan.price or 0):
                    price_changed = True
                plan.price = new_price
            if 'questions_per_month' in data:
                plan.questions_per_month = data['questions_per_month']
            if 'billing_cycle' in data:
                plan.billing_cycle = data['billing_cycle']
            if 'badge' in data:
                plan.badge = data['badge']
            if 'is_active' in data:
                plan.is_active = data['is_active']
            if 'features' in data:
                plan.features = data['features']
                
            import stripe
            
            # If price changed or there is no stripe_price_id, create a new Product and Price in Stripe
            if (price_changed or not plan.stripe_price_id) and plan.price and float(plan.price) > 0:
                product = stripe.Product.create(
                    name=plan.name,
                    description=f"{plan.plantype} - {plan.questions_per_month} queries/mo"
                )
                interval = 'year' if plan.billing_cycle and plan.billing_cycle.lower() == 'yearly' else 'month'
                price_obj = stripe.Price.create(
                    unit_amount=int(float(plan.price) * 100),
                    currency='usd',
                    recurring={"interval": interval},
                    product=product.id,
                )
                plan.stripe_price_id = price_obj.id
                
            plan.save()
            return Response({"message": "Plan updated successfully!", "stripe_price_id": plan.stripe_price_id}, status=status.HTTP_200_OK)
        except Plans.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            plan_id = request.data.get('plan_id')
            if not plan_id:
                return Response({'error': 'Plan ID is required'}, status=status.HTTP_400_BAD_REQUEST)
                
            plan = Plans.objects.get(id=plan_id)
            if not plan.stripe_price_id:
                return Response({'error': 'This plan does not have a valid Stripe price ID.'}, status=status.HTTP_400_BAD_REQUEST)

            # Prevent purchasing if the user has an active non-free subscription
            from .models import UserSubscription
            active_sub = UserSubscription.objects.filter(user=request.user, status='active').exclude(plan__plantype__iexact='free').exists()
            if active_sub:
                return Response(
                    {'error': 'You already have an active subscription. You cannot purchase another plan until your current subscription ends.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            success_url = request.data.get('success_url', os.getenv("PAYMENT_SUCCESS_URL", "http://localhost:3000/payment-success"))
            cancel_url = request.data.get('cancel_url', os.getenv("PAYMENT_CANCEL_URL", "http://localhost:3000/payment-cancel"))

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price': plan.stripe_price_id,
                        'quantity': 1,
                    },
                ],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=request.user.id,
                metadata={
                    'plan_id': plan.id,
                    'plantype': plan.plantype
                }
            )
            return Response({'checkout_url': checkout_session.url})
        except Plans.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

        event = None
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Handle the checkout.session.completed event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            user_id = session.get("client_reference_id")
            metadata = session.get("metadata", {})
            plantype = metadata.get("plantype")
            plan_id = metadata.get("plan_id")
            
            customer_id = session.get("customer")
            subscription_id = session.get("subscription")
            
            if user_id and plantype:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(id=user_id)
                    user.plantype = plantype
                    if customer_id:
                        user.stripe_customer_id = customer_id
                    if subscription_id:
                        user.stripe_subscription_id = subscription_id
                    user.save()
                    
                    if plan_id:
                        from .models import UserSubscription, Plans
                        plan_obj = Plans.objects.filter(id=plan_id).first()
                        if plan_obj:
                            UserSubscription.objects.create(
                                user=user,
                                plan=plan_obj,
                                stripe_subscription_id=subscription_id,
                                stripe_customer_id=customer_id,
                                status='active'
                            )
                except User.DoesNotExist:
                    pass
            
        return Response(status=status.HTTP_200_OK)


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        
        if not user.stripe_subscription_id:
            return Response({"error": "No active Stripe subscription found for this user."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # Cancel the subscription in Stripe
            deleted_subscription = stripe.Subscription.delete(user.stripe_subscription_id)
            
            from .models import UserSubscription
            from django.utils import timezone
            sub = UserSubscription.objects.filter(stripe_subscription_id=user.stripe_subscription_id, status='active').first()
            if sub:
                sub.status = 'cancelled'
                sub.end_date = timezone.now()
                sub.save()
            
            # Update user locally
            user.plantype = 'free' # or import PlanType and use PlanType.FREE.value
            user.stripe_subscription_id = None
            user.save()
            
            return Response({"message": "Subscription cancelled successfully."}, status=status.HTTP_200_OK)
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": "An error occurred while cancelling the subscription."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserCurrentPlanView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        
        response_data = {
            "current_plan": user.plantype,
            "plan_details": None,
            "status": "inactive",
            "start_date": None,
            "end_date": None,
            "expire_date": None,
            "next_billing_date": None
        }
        
        try:
            from .models import UserSubscription, Plans
            # Fetch active or cancelled subscription from DB
            active_sub = UserSubscription.objects.filter(user=user, status__in=['active', 'cancelled']).order_by('-start_date').first()
            
            if active_sub and active_sub.plan:
                plan = active_sub.plan
                if active_sub.status == 'cancelled':
                    response_data["current_plan"] = "free"
                    response_data["status"] = "cancel"
                else:
                    response_data["current_plan"] = plan.plantype
                    response_data["status"] = active_sub.status

                response_data["plan_details"] = {
                    "name": plan.name,
                    "price": plan.price,
                    "billing_cycle": plan.billing_cycle,
                    "questions_per_month": plan.questions_per_month,
                    "features": plan.features
                }
                response_data["start_date"] = active_sub.start_date.isoformat() if active_sub.start_date else None
                
                # Fetch end date from Stripe if available
                end_date_str = None
                if active_sub.stripe_subscription_id:
                    import stripe
                    try:
                        stripe_sub = stripe.Subscription.retrieve(active_sub.stripe_subscription_id)
                        from datetime import datetime
                        current_period_end = datetime.fromtimestamp(stripe_sub.current_period_end)
                        end_date_str = current_period_end.isoformat()
                        
                        if stripe_sub.cancel_at_period_end:
                            response_data["status"] = "cancel"
                    except Exception:
                        end_date_str = active_sub.end_date.isoformat() if active_sub.end_date else None
                else:
                    end_date_str = active_sub.end_date.isoformat() if active_sub.end_date else None

                # Fallback: calculate dynamically based on start_date + 1 month if end_date_str is still null
                if not end_date_str:
                    from django.utils import timezone
                    import datetime
                    import calendar
                    
                    ref_date = active_sub.start_date or timezone.now()
                    if ref_date.month == 12:
                        next_billing_dt = datetime.datetime(ref_date.year + 1, 1, ref_date.day, tzinfo=ref_date.tzinfo)
                    else:
                        next_month_num = ref_date.month + 1
                        _, max_days = calendar.monthrange(ref_date.year, next_month_num)
                        next_day = min(ref_date.day, max_days)
                        next_billing_dt = datetime.datetime(ref_date.year, next_month_num, next_day, tzinfo=ref_date.tzinfo)
                    
                    end_date_str = next_billing_dt.isoformat()

                response_data["end_date"] = end_date_str
                response_data["expire_date"] = end_date_str
                
                # Next billing date is the same as the end date if the subscription is active and not cancelling
                if response_data["status"] not in ["cancelled", "cancels_at_period_end", "cancel"]:
                    response_data["next_billing_date"] = end_date_str
                else:
                    response_data["next_billing_date"] = None
            else:
                free_plan = Plans.objects.filter(plantype__iexact='free').first()
                if free_plan:
                    response_data["plan_details"] = {
                        "name": free_plan.name,
                        "price": free_plan.price,
                        "billing_cycle": free_plan.billing_cycle,
                        "questions_per_month": free_plan.questions_per_month,
                        "features": free_plan.features
                    }
                response_data["status"] = "active" # Free is always active
                
                # Set dynamic monthly cycle dates for the free plan
                from django.utils import timezone
                import datetime
                
                now = timezone.now()
                start_of_month = datetime.datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
                if now.month == 12:
                    next_month = datetime.datetime(now.year + 1, 1, 1, tzinfo=now.tzinfo)
                else:
                    next_month = datetime.datetime(now.year, now.month + 1, 1, tzinfo=now.tzinfo)
                
                response_data["start_date"] = start_of_month.isoformat()
                response_data["end_date"] = next_month.isoformat()
                response_data["expire_date"] = next_month.isoformat()
                response_data["next_billing_date"] = next_month.isoformat()

            # Calculate user's monthly query limit and usage stats
            limit = None
            plan_details = response_data.get("plan_details")
            if plan_details:
                limit = plan_details.get("questions_per_month")
            else:
                plantype = getattr(user, 'plantype', 'free')
                LIMIT_MAPPING = {
                    'free': 5,
                    'core': 30,
                    'builder': 75,
                    'anchor': -1,
                }
                limit = LIMIT_MAPPING.get(plantype, 5)

            from chatsystem.models import Message
            from django.utils import timezone
            import datetime
            
            now = timezone.now()
            start_of_month = datetime.datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
            sent_count = Message.objects.filter(
                sender=user,
                is_deleted=False,
                created_at__gte=start_of_month
            ).count()

            if limit == -1:
                remaining = "Unlimited"
                total = "Unlimited"
            else:
                remaining = max(0, limit - sent_count)
                total = limit

            response_data["usage"] = {
                "used_questions": sent_count,
                "remaining_questions": remaining,
                "total_questions": total
            }
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        return Response(response_data, status=status.HTTP_200_OK)


class RunTestsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        import io
        import sys
        from django.test.utils import get_runner
        from django.conf import settings

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stream = io.StringIO()
        sys.stdout = stream
        sys.stderr = stream

        try:
            TestRunner = get_runner(settings)
            test_runner = TestRunner(verbosity=2, interactive=False, failfast=False)
            failures = test_runner.run_tests(["chatsystem"])
        except Exception as e:
            import traceback
            traceback.print_exc(file=stream)
            failures = -1
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        output = stream.getvalue()
        return Response({
            "failures": failures,
            "output": output
        }, status=status.HTTP_200_OK)


class SyncCatalogView(APIView):
    """Temporary endpoint: populate missing BMC catalog products and sync vector store."""
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        from admin_dashboard.models import Product
        from django.core.files.base import ContentFile
        from chatsystem.ai import sync_all_products
        from admin_dashboard.management.commands.populate_products import BMC_CATALOG

        existing_names = set(Product.objects.values_list("name", flat=True))
        created, skipped, errors = [], [], []

        for item in BMC_CATALOG:
            name = item["name"]
            if name in existing_names:
                skipped.append(name)
                continue
            try:
                product = Product(
                    name=name,
                    product_type=item["product_type"],
                    link=item.get("link") or "https://blackmillennialcafe.com",
                    description=item.get("description") or "",
                    product_price=item.get("price"),
                    is_published=True,
                )
                product.save()
                product.product_image.save(
                    "bmc_default.jpg",
                    ContentFile(b"\xff\xd8\xff\xe0" + b"\x00" * 100),
                    save=True,
                )
                created.append(name)
            except Exception as e:
                errors.append({"name": name, "error": str(e)})

        # Sync ALL products (including pre-existing ones) into vector store
        sync_result = sync_all_products()

        return Response({
            "status": "done",
            "created": len(created),
            "created_names": created,
            "skipped": len(skipped),
            "errors": errors,
            "vector_store_sync": sync_result,
        }, status=status.HTTP_200_OK)

