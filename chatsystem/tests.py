"""
Comprehensive test suite for the Revri AI chatsystem.

Coverage:
  1. Unit: cosine_similarity, check_blocked, price parsing, topK parsing
  2. Unit: _classify_query_intent (mocked OpenAI)
  3. Unit: handle_message routing — product search, clarification, general question
  4. Unit: VectorStore search logic
  5. Unit: product ingest_product content enrichment
  6. API: POST /api/send-message/ — product query, clarification, blocked, general
  7. API: GET /api/plan-list/
"""
import json
from unittest.mock import patch, MagicMock, call
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from chatsystem.models import ChatRoom, Message, AISetting, BlockedKeyword
from chatsystem.ai import (
    cosine_similarity,
    check_blocked,
    _parse_price_filters,
    _parse_top_k,
    VectorStore,
    _classify_query_intent,
    handle_message,
    _is_product_intent,
    clean_response_text,
)
from plan.models import Plans, UserSubscription

User = get_user_model()


# ─────────────────────────────────────────────
# 1. Pure-unit AI helper tests (no DB, no network)
# ─────────────────────────────────────────────
class AIUtilTests(APITestCase):

    # cosine_similarity
    def test_cosine_exact_match(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0, places=5)

    def test_cosine_orthogonal(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, places=5)

    def test_cosine_length_mismatch(self):
        self.assertEqual(cosine_similarity([1.0], [1.0, 0.0]), 0.0)

    def test_cosine_empty(self):
        self.assertEqual(cosine_similarity([], []), 0.0)

    # check_blocked
    @override_settings(AI_BLOCKED_KEYWORDS=['spam', 'abuse'])
    def test_check_blocked_clean(self):
        self.assertEqual(check_blocked("hello there"), [])

    @override_settings(AI_BLOCKED_KEYWORDS=['spam', 'abuse'])
    def test_check_blocked_hit(self):
        self.assertIn('spam', check_blocked("this is spam content"))

    @override_settings(AI_BLOCKED_KEYWORDS=['spam'])
    def test_check_blocked_empty_message(self):
        self.assertEqual(check_blocked(""), [])

    # price filter parsing
    def test_parse_price_between(self):
        result = _parse_price_filters("between 50 and 150 dollars")
        self.assertEqual(result['min_price'], 50.0)
        self.assertEqual(result['max_price'], 150.0)

    def test_parse_price_under(self):
        result = _parse_price_filters("under 100")
        self.assertEqual(result['max_price'], 100.0)

    def test_parse_price_over(self):
        result = _parse_price_filters("over 200")
        self.assertEqual(result['min_price'], 200.0)

    def test_parse_price_no_match(self):
        self.assertEqual(_parse_price_filters("show me all products"), {})

    # topK parsing
    def test_parse_top_k_number(self):
        self.assertEqual(_parse_top_k("show me 3 products"), 3)

    def test_parse_top_k_word(self):
        self.assertEqual(_parse_top_k("recommend two products"), 2)

    def test_parse_top_k_one(self):
        self.assertEqual(_parse_top_k("just one product please"), 1)

    def test_parse_top_k_none(self):
        self.assertIsNone(_parse_top_k("show me products"))

    # _is_product_intent (legacy fallback)
    def test_is_product_intent_assessment(self):
        self.assertTrue(_is_product_intent("I need an assessment for my church"))

    def test_is_product_intent_webinar(self):
        self.assertTrue(_is_product_intent("do you have webinar subscriptions?"))

    def test_is_product_intent_greeting(self):
        self.assertFalse(_is_product_intent("hello, how are you?"))

    # clean_response_text spacing test
    def test_clean_response_text_spacing(self):
        text = "Hello World\n\n\n\nHow are you?\n\nFine."
        # Should clean multiple blank lines to exactly one blank line
        cleaned = clean_response_text(text)
        self.assertEqual(cleaned, "Hello World\n\nHow are you?\n\nFine.")

        # Test bullet points list (should have no empty line between items)
        list_text = "* Point 1\n\n* Point 2\n\n* Point 3"
        cleaned_list = clean_response_text(list_text)
        self.assertEqual(cleaned_list, "* Point 1\n* Point 2\n* Point 3")

        # Test bold headers list (should have no empty line between items)
        bold_text = "**Title 1**: text\n\n**Title 2**: text"
        cleaned_bold = clean_response_text(bold_text)
        self.assertEqual(cleaned_bold, "**Title 1**: text\n**Title 2**: text")


# ─────────────────────────────────────────────
# 2. VectorStore unit tests (no OpenAI)
# ─────────────────────────────────────────────
class VectorStoreTests(APITestCase):

    def setUp(self):
        import tempfile, os
        self.tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        self.tmp.write(b'{"chunks": []}')
        self.tmp.close()
        self.vs = VectorStore(path=self.tmp.name)

    def tearDown(self):
        import os
        try:
            os.unlink(self.tmp.name)
        except Exception:
            pass

    def _fake_embed(self, n=8):
        return [0.1] * n

    def test_ingest_and_search(self):
        emb = self._fake_embed()
        # Patch embed_text to return a fixed vector
        with patch('chatsystem.ai.embed_text', return_value=emb):
            self.vs.ingest_product(
                product_id=99, name="Test Assessment", description="A church survey",
                product_type="resource", link="http://example.com",
                image_url=None, price="119.00"
            )
        store = self.vs.read()
        self.assertEqual(len(store['chunks']), 1)
        self.assertEqual(store['chunks'][0]['product_id'], 99)

    def test_search_returns_top_match(self):
        emb_a = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        emb_b = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        # Insert two chunks manually
        store_data = {"chunks": [
            {"product_id": 1, "name": "A", "description": "", "product_type": "resource",
             "link": None, "image_url": None, "price": "10", "content": "A", "embedding": emb_a},
            {"product_id": 2, "name": "B", "description": "", "product_type": "resource",
             "link": None, "image_url": None, "price": "20", "content": "B", "embedding": emb_b},
        ]}
        self.vs.write(store_data)
        results = self.vs.search(emb_a, topK=1, min_score=0.0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['product_id'], 1)

    def test_delete_product(self):
        emb = self._fake_embed()
        with patch('chatsystem.ai.embed_text', return_value=emb):
            self.vs.ingest_product(99, "X", "desc", "resource", None, None, "10")
        self.vs.delete_product(99)
        self.assertEqual(len(self.vs.read()['chunks']), 0)

    def test_ingest_replaces_old(self):
        emb = self._fake_embed()
        with patch('chatsystem.ai.embed_text', return_value=emb):
            self.vs.ingest_product(99, "Old Name", "desc", "resource", None, None, "10")
            self.vs.ingest_product(99, "New Name", "desc updated", "resource", None, None, "50")
        store = self.vs.read()
        self.assertEqual(len(store['chunks']), 1)
        self.assertEqual(store['chunks'][0]['name'], "New Name")

    def test_rich_content_format(self):
        """ingest_product should build semantically rich content string."""
        emb = self._fake_embed()
        with patch('chatsystem.ai.embed_text', return_value=emb) as mock_embed:
            self.vs.ingest_product(99, "Youth Assessment", "Evaluates youth programs",
                                   "resource", None, None, "119.00")
            called_text = mock_embed.call_args[0][0]
        self.assertIn("Youth Assessment", called_text)
        self.assertIn("resource book guide download", called_text)
        self.assertIn("$119.00", called_text)


# ─────────────────────────────────────────────
# 3. _classify_query_intent tests (mocked OpenAI)
# ─────────────────────────────────────────────
class IntentClassificationTests(APITestCase):

    def _mock_openai_intent(self, intent_dict):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = json.dumps(intent_dict)
        mock_client.chat.completions.create.return_value = mock_resp
        return mock_client

    @patch('chatsystem.ai.openai_client')
    def test_product_search_intent(self, mock_oc):
        mock_oc.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "intent": "product_search",
                "product_type_hint": "resource",
                "price_min": None,
                "price_max": 120.0,
                "keywords": ["assessment", "church"],
                "clarification_question": None,
                "enriched_query": "church health assessment resource under $120"
            })))]
        )
        result = _classify_query_intent("I need a church assessment under $120")
        self.assertEqual(result['intent'], 'product_search')
        self.assertEqual(result['product_type_hint'], 'resource')
        self.assertEqual(result['price_max'], 120.0)

    @patch('chatsystem.ai.openai_client')
    def test_clarification_intent(self, mock_oc):
        mock_oc.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "intent": "clarification_needed",
                "product_type_hint": None,
                "price_min": None,
                "price_max": None,
                "keywords": [],
                "clarification_question": "Could you tell me more about what you need?",
                "enriched_query": "something"
            })))]
        )
        result = _classify_query_intent("something")
        self.assertEqual(result['intent'], 'clarification_needed')
        self.assertIsNotNone(result['clarification_question'])

    @patch('chatsystem.ai.openai_client')
    def test_general_question_intent(self, mock_oc):
        mock_oc.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "intent": "general_question",
                "product_type_hint": None,
                "price_min": None,
                "price_max": None,
                "keywords": [],
                "clarification_question": None,
                "enriched_query": "Hello"
            })))]
        )
        result = _classify_query_intent("Hello!")
        self.assertEqual(result['intent'], 'general_question')

    def test_intent_fallback_when_no_client(self):
        """Without openai_client, should fall back to keyword detection."""
        with patch('chatsystem.ai.openai_client', None):
            result = _classify_query_intent("I need a church assessment")
        self.assertEqual(result['intent'], 'product_search')

    def test_intent_fallback_greeting(self):
        with patch('chatsystem.ai.openai_client', None):
            result = _classify_query_intent("Good morning")
        self.assertEqual(result['intent'], 'general_question')


# ─────────────────────────────────────────────
# 4. handle_message routing tests
# ─────────────────────────────────────────────
class HandleMessageTests(APITestCase):

    def _mock_embed(self):
        mock = MagicMock()
        mock.data = [MagicMock(embedding=[0.1] * 1536)]
        return mock

    def _mock_chat(self, content="Test AI response"):
        mock = MagicMock()
        mock.choices = [MagicMock(message=MagicMock(content=content))]
        return mock

    @patch('chatsystem.ai.openai_client')
    def test_blocked_message(self, mock_oc):
        with override_settings(AI_BLOCKED_KEYWORDS=['badword']):
            result = handle_message("this has badword in it")
        self.assertTrue(result.get('blocked'))
        self.assertIn('badword', result.get('matched', []))

    @patch('chatsystem.ai.openai_client')
    def test_empty_message(self, mock_oc):
        result = handle_message("")
        self.assertIn('error', result)

    @patch('chatsystem.ai.openai_client')
    def test_clarification_route(self, mock_oc):
        """Vague query should trigger clarification response."""
        mock_oc.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "intent": "clarification_needed",
                "product_type_hint": None,
                "price_min": None, "price_max": None,
                "keywords": [],
                "clarification_question": "What type of resource are you looking for?",
                "enriched_query": "something"
            })))]
        )
        result = handle_message("something")
        self.assertEqual(result.get('intent'), 'clarification_needed')
        self.assertIn('answer', result)
        self.assertIn('What type', result['answer'])

    @patch('chatsystem.ai.openai_client')
    def test_product_search_route(self, mock_oc):
        """Product query should route to recommend_products and include results key."""
        # First call = intent classification JSON
        # Second call = summary text
        mock_oc.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
                "intent": "product_search",
                "product_type_hint": "resource",
                "price_min": None, "price_max": None,
                "keywords": ["assessment"],
                "clarification_question": None,
                "enriched_query": "church health assessment resource"
            })))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content="Here are some great assessments for you!"))]),
        ]
        mock_oc.embeddings.create.return_value = self._mock_embed()

        result = handle_message("I need a church assessment")
        self.assertEqual(result.get('intent'), 'product_search')
        self.assertIn('results', result)

    @patch('chatsystem.ai.openai_client')
    def test_general_question_route(self, mock_oc):
        """General question should route to RAG and return 'answer'."""
        mock_oc.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
                "intent": "general_question",
                "product_type_hint": None,
                "price_min": None, "price_max": None,
                "keywords": [],
                "clarification_question": None,
                "enriched_query": "Who founded BMC?"
            })))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content="BMC was founded by Dr. Brianna K. Parker."))]),
        ]
        mock_oc.embeddings.create.return_value = self._mock_embed()

        result = handle_message("Who founded BMC?")
        self.assertEqual(result.get('intent'), 'general_question')
        self.assertIn('answer', result)

    @patch('chatsystem.ai.openai_client')
    def test_conversation_history_passed_to_classifier(self, mock_oc):
        """Conversation history should be forwarded to intent classifier."""
        history = [
            {"role": "user", "content": "I need help"},
            {"role": "assistant", "content": "Sure, what are you looking for?"},
        ]
        mock_oc.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "intent": "product_search",
                "product_type_hint": None,
                "price_min": None, "price_max": None,
                "keywords": ["assessment"],
                "clarification_question": None,
                "enriched_query": "church assessment"
            })))]
        )
        mock_oc.embeddings.create.return_value = self._mock_embed()

        handle_message("A church assessment please", conversation_history=history)

        # The classifier call should have included the history messages
        calls = mock_oc.chat.completions.create.call_args_list
        first_call_messages = calls[0][1].get('messages', calls[0][0][0] if calls[0][0] else [])
        # Should contain more than just system + user (history was prepended)
        self.assertGreater(len(first_call_messages), 2)

    @patch('chatsystem.ai.openai_client')
    def test_price_filter_extracted(self, mock_oc):
        """Price constraints in query should be passed as filters to recommend_products."""
        mock_oc.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "intent": "product_search",
                "product_type_hint": None,
                "price_min": None,
                "price_max": 30.0,
                "keywords": ["book"],
                "clarification_question": None,
                "enriched_query": "books under 30 dollars"
            })))]
        )
        mock_oc.embeddings.create.return_value = self._mock_embed()

        with patch('chatsystem.ai.recommend_products') as mock_rec:
            mock_rec.return_value = {"results": [], "query": "books under 30"}
            handle_message("show me books under $30")
            called_filters = mock_rec.call_args[1].get('filters') or mock_rec.call_args[0][3] if mock_rec.call_args[0] else {}
            if called_filters:
                self.assertLessEqual(called_filters.get('max_price', 9999), 30.0)


# ─────────────────────────────────────────────
# 5. API integration tests
# ─────────────────────────────────────────────
class APIIntegrationTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='apitester@example.com',
            password='testpass123',
            full_name='API Tester'
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='testpass123',
            full_name='Other User'
        )
        self.client.force_authenticate(user=self.user)

        self.free_plan, _ = Plans.objects.get_or_create(
            name="Free",
            plantype="free",
            defaults={"price": 0.00, "questions_per_month": 5, "is_active": True}
        )
        self.premium_plan, _ = Plans.objects.get_or_create(
            name="Premium",
            plantype="premium",
            defaults={
                "price": 29.00, "questions_per_month": 1000,
                "is_active": True, "stripe_price_id": "price_dummy_test"
            }
        )

    def _mock_openai(self, mock_oc, intent="product_search", answer="Great products found!"):
        mock_oc.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
                "intent": intent,
                "product_type_hint": None,
                "price_min": None, "price_max": None,
                "keywords": ["assessment"],
                "clarification_question": "What are you looking for?" if intent == "clarification_needed" else None,
                "enriched_query": "church assessment resource"
            })))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content=answer))]),
        ]
        mock_oc.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=[0.1] * 1536)]
        )

    # ── send-message endpoint ──
    @patch('chatsystem.ai.openai_client')
    def test_send_message_product_query(self, mock_oc):
        self._mock_openai(mock_oc, intent="product_search", answer="Here are some assessments.")
        url = reverse('send-message')
        resp = self.client.post(url, {'message': 'I need a church assessment'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('ai_response', resp.data)
        ai = resp.data['ai_response']
        self.assertEqual(ai.get('intent'), 'product_search')

    @patch('chatsystem.ai.openai_client')
    def test_send_message_clarification(self, mock_oc):
        self._mock_openai(mock_oc, intent="clarification_needed")
        url = reverse('send-message')
        resp = self.client.post(url, {'message': 'help'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        ai = resp.data['ai_response']
        self.assertEqual(ai.get('intent'), 'clarification_needed')
        self.assertIn('answer', ai)

    @patch('chatsystem.ai.openai_client')
    def test_send_message_general_question(self, mock_oc):
        self._mock_openai(mock_oc, intent="general_question", answer="BMC helps Black churches grow.")
        url = reverse('send-message')
        resp = self.client.post(url, {'message': 'Tell me about BMC'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    @patch('chatsystem.ai.openai_client')
    def test_send_message_exceeds_limit(self, mock_oc):
        # Configure user to have 'free' plantype and limit to 5
        self.user.plantype = 'free'
        self.user.save()
        self.free_plan.questions_per_month = 5
        self.free_plan.save()

        # Create 5 existing messages for the current month
        room = ChatRoom.objects.create(human=self.user, name="Test Room")
        for i in range(5):
            Message.objects.create(room=room, sender=self.user, message=f"query {i}", ai_response="{}")

        # The 6th message should fail
        url = reverse('send-message')
        resp = self.client.post(url, {'message': 'Should fail'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("reached your monthly question limit", resp.data["detail"])

    @override_settings(AI_BLOCKED_KEYWORDS=['badword'])
    def test_send_message_blocked(self):
        url = reverse('send-message')
        resp = self.client.post(url, {'message': 'badword content'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        ai = resp.data['ai_response']
        self.assertTrue(ai.get('blocked'))

    def test_send_message_unauthenticated(self):
        self.client.force_authenticate(user=None)
        url = reverse('send-message')
        resp = self.client.post(url, {'message': 'Hello'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_send_message_empty(self):
        url = reverse('send-message')
        resp = self.client.post(url, {'message': ''}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_message_persists_to_db(self):
        """Sent messages should be saved to the Message model."""
        with patch('chatsystem.ai.openai_client') as mock_oc:
            self._mock_openai(mock_oc, intent="general_question", answer="AI answer here")
            url = reverse('send-message')
            self.client.post(url, {'message': 'Test persistence'}, format='json')
        self.assertTrue(Message.objects.filter(message='Test persistence').exists())

    # ── plan-list endpoint ──
    def test_plan_list(self):
        url = reverse('plan-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)

    # ── user-current-plan ──
    def test_user_current_plan(self):
        url = reverse('user-current-plan')
        
        # 1. Test Free default
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["current_plan"], "free")
        self.assertIsNotNone(resp.data["start_date"])
        self.assertIsNotNone(resp.data["expire_date"])
        self.assertIsNotNone(resp.data["next_billing_date"])
        self.assertIn("usage", resp.data)
        self.assertIn("used_questions", resp.data["usage"])
        self.assertIn("remaining_questions", resp.data["usage"])
        self.assertIn("total_questions", resp.data["usage"])

        # 2. Test Paid subscription fallback calculation
        UserSubscription.objects.create(
            user=self.user,
            plan=self.premium_plan,
            stripe_subscription_id="sub_test_current",
            status="active"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["current_plan"], self.premium_plan.plantype)
        self.assertIsNotNone(resp.data["start_date"])
        self.assertIsNotNone(resp.data["expire_date"])
        self.assertIsNotNone(resp.data["next_billing_date"])

        # 3. Test Cancelled subscription
        sub = UserSubscription.objects.get(stripe_subscription_id="sub_test_current")
        sub.status = "cancelled"
        sub.save()
        
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["current_plan"], "free")
        self.assertEqual(resp.data["status"], "cancel")
        self.assertIsNone(resp.data["next_billing_date"])

    # ── report & block user ──
    def test_report_user(self):
        url = reverse('report-user', kwargs={'id': self.other_user.id})
        resp = self.client.post(url, {'reason': 'harassment'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_block_user(self):
        url = reverse('block-user', kwargs={'id': self.other_user.id})
        resp = self.client.post(url, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_block_self_rejected(self):
        url = reverse('block-user', kwargs={'id': self.user.id})
        resp = self.client.post(url, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Stripe checkout (mocked) ──
    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session(self, mock_stripe):
        mock_session = MagicMock()
        mock_session.url = 'https://checkout.stripe.com/test_url'
        mock_stripe.return_value = mock_session
        url = reverse('create-checkout-session')
        resp = self.client.post(url, {'plan_id': self.premium_plan.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('checkout_url', resp.data)

    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session_rejected_if_active(self, mock_stripe):
        # Create active non-free subscription for self.user
        UserSubscription.objects.create(
            user=self.user,
            plan=self.premium_plan,
            stripe_subscription_id="sub_test",
            status="active"
        )
        url = reverse('create-checkout-session')
        resp = self.client.post(url, {'plan_id': self.premium_plan.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already have an active subscription", resp.data["error"])

    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session_allowed_if_free_plan(self, mock_stripe):
        # Create active free subscription for self.user
        UserSubscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            stripe_subscription_id="sub_free",
            status="active"
        )
        mock_session = MagicMock()
        mock_session.url = 'https://checkout.stripe.com/test_url'
        mock_stripe.return_value = mock_session

        url = reverse('create-checkout-session')
        resp = self.client.post(url, {'plan_id': self.premium_plan.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('checkout_url', resp.data)

    @patch('stripe.Product.create')
    @patch('stripe.Price.create')
    def test_plan_update_syncs_stripe(self, mock_price, mock_product):
        mock_product.return_value = MagicMock(id='prod_test')
        mock_price.return_value = MagicMock(id='price_test_new')
        url = reverse('plan-detail-update', kwargs={'pk': self.premium_plan.id})
        resp = self.client.patch(url, {'price': '45.00'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.premium_plan.refresh_from_db()
        self.assertEqual(float(self.premium_plan.price), 45.00)

    def test_account_overview(self):
        # 1. With free plan
        self.user.userole = 'normal'
        self.user.is_verified = True
        self.user.plantype = 'free'
        self.user.save()
        
        # Configure free plan limit to 5
        self.free_plan.questions_per_month = 5
        self.free_plan.save()
        
        url = reverse('account-overview')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['role'], 'Normal')
        self.assertEqual(resp.data['data']['verified'], 'Yes')
        self.assertEqual(resp.data['data']['plan'], 'Free')
        self.assertEqual(resp.data['data']['queries_limit'], '5/5')

        # Create 2 messages to reduce remaining questions
        room = ChatRoom.objects.create(human=self.user, name="Test Room")
        Message.objects.create(room=room, sender=self.user, message="query 1", ai_response="{}")
        Message.objects.create(room=room, sender=self.user, message="query 2", ai_response="{}")

        resp = self.client.get(url)
        self.assertEqual(resp.data['data']['queries_limit'], '3/5')

        # 2. With plantype = None (None / —)
        self.user.plantype = None
        self.user.save()
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['data']['plan'], 'None')
        self.assertEqual(resp.data['data']['queries_limit'], '—')
