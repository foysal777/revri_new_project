import os
import django
import traceback

try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_root.settings')
    django.setup()

    from chatsystem.models import UserQueryLog
    with open('scratch_log.txt', 'w') as f:
        f.write("Logs found:\n")
        for log in UserQueryLog.objects.all().order_by('-created_at')[:5]:
            f.write(f"Query: {log.query_text}\nResponse: {log.response_text}\n---\n")
except Exception as e:
    with open('scratch_log.txt', 'w') as f:
        f.write(f"Error: {str(e)}\n")
        f.write(traceback.format_exc())
