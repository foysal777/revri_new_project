import json

from channels.generic.websocket import AsyncWebsocketConsumer
from plan.enums import PlanType


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.groups_to_join = {f"user_{self.user.id}"}
        self.groups_to_join.update(self._get_plan_groups())

        for group_name in self.groups_to_join:
            await self.channel_layer.group_add(group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        for group_name in getattr(self, 'groups_to_join', set()):
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            await self.send(text_data=json.dumps({'message': 'pong'}))

    async def send_notification(self, event):
        await self.send(text_data=json.dumps(event['notification']))

    def _get_plan_groups(self):
        plan_groups = set()
        plan_types = set()

        if hasattr(self.user, 'plantype') and self.user.plantype:
            plan_types.add(self.user.plantype)

        if hasattr(self.user, 'plans'):
            try:
                for plan in self.user.plans.all():
                    if getattr(plan, 'plantype', None):
                        plan_types.add(plan.plantype)
            except Exception:
                pass

        valid_plan_values = {choice[0] for choice in PlanType.choices()}
        for plan_type in plan_types:
            if plan_type in valid_plan_values:
                plan_groups.add(f"plan_{plan_type}")

        return plan_groups
