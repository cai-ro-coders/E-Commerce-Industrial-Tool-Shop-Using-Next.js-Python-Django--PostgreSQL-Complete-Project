from django.db.models import Avg, Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrStaff
from apps.core.utils import log_activity

from .models import Review
from .serializers import ReviewSerializer


def is_staff(user):
    return user.is_authenticated and (user.role in ("admin", "staff") or user.is_superuser)


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    filterset_fields = ["product", "rating", "status"]
    search_fields = ["title", "comment", "product__name", "user__email"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedOrReadOnly()]
        if self.action in ("moderate",):
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Review.objects.select_related("user", "product").prefetch_related("product__images")
        user = self.request.user
        if is_staff(user):
            return qs
        if user.is_authenticated:
            return qs.filter(Q(status="approved") | Q(user=user))
        return qs.filter(status="approved")

    def perform_create(self, serializer):
        review = serializer.save(user=self.request.user)
        log_activity(self.request.user, "review.created", f"Reviewed {review.product.name}", "review", review.pk, self.request)

    def update(self, request, *args, **kwargs):
        review = self.get_object()
        if not is_staff(request.user) and review.user != request.user:
            raise PermissionDenied("You can only edit your own review.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        review = self.get_object()
        if not is_staff(request.user) and review.user != request.user:
            raise PermissionDenied("You can only delete your own review.")
        log_activity(request.user, "review.deleted", f"Deleted review for {review.product.name}", "review", review.pk, request)
        review.delete()
        return Response({"success": True, "message": "Review deleted."})

    @action(detail=True, methods=["patch"])
    def moderate(self, request, pk=None):
        review = self.get_object()
        new_status = request.data.get("status")
        if new_status not in ("approved", "rejected", "pending"):
            return Response(
                {"success": False, "message": "Invalid moderation status."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        review.status = new_status
        review.save(update_fields=["status"])
        log_activity(request.user, "review.moderated", f"Review #{review.pk} -> {new_status}", "review", review.pk, request)
        return Response(
            {"success": True, "message": f"Review {new_status}.", "data": ReviewSerializer(review, context={"request": request}).data}
        )

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = Review.objects.all()
        return Response(
            {
                "success": True,
                "data": {
                    "total": qs.count(),
                    "pending": qs.filter(status="pending").count(),
                    "approved": qs.filter(status="approved").count(),
                    "rejected": qs.filter(status="rejected").count(),
                    "average_rating": round(qs.aggregate(avg=Avg("rating"))["avg"] or 0, 2),
                    "rating_breakdown": list(
                        qs.values("rating").annotate(count=Count("id")).order_by("rating")
                    ),
                },
            }
        )
