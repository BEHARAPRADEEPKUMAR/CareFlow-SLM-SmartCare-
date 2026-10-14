from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .services import run_chat


class ChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = str(request.data.get("message", "")).strip()
        if not message:
            return Response({"error": "message is required"}, status=400)

        confirmation = request.data.get("confirmation")
        conversation_id = str(
            request.data.get("conversation_id", "")
        ).strip() or None

        result = run_chat(
            message,
            user=request.user,
            confirmation=confirmation,
            conversation_id=conversation_id,
        )
        return Response(result)
