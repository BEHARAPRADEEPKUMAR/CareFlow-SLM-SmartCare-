from rest_framework.views import APIView
from rest_framework.response import Response
from .services import check_safety
class SafetyCheckView(APIView):
    def post(self, request):
        return Response(check_safety(str(request.data.get("message",""))))
