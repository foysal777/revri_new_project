from rest_framework.pagination import BasePagination
from rest_framework.response import Response


# 10 products per page
class CustomPagination(BasePagination):
    page_size = 10

    def paginate_queryset(self, queryset, request, view=None):
        page_number = request.query_params.get('page', 1)
        try:
            page_number = int(page_number)
        except ValueError:
            page_number = 1

        start_index = (page_number - 1) * self.page_size
        end_index = start_index + self.page_size
        return queryset[start_index:end_index]

    def get_paginated_response(self, data):
        return Response({
            'count': len(data),
            'results': data,
        })