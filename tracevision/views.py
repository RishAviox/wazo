from rest_framework import generics, permissions
from .models import MatchDataTracevision
from .serializers import MatchDataTracevisionSerializer


class MatchDataTracevisionListCreateView(generics.ListCreateAPIView):
    queryset = MatchDataTracevision.objects.all()
    serializer_class = MatchDataTracevisionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)



class MatchDataTracevisionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MatchDataTracevision.objects.all()
    serializer_class = MatchDataTracevisionSerializer
    permission_classes = [permissions.IsAuthenticated]
