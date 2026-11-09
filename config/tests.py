from django.test import SimpleTestCase
from drf_spectacular.generators import SchemaGenerator


class SchemaTests(SimpleTestCase):
    def test_custom_operations_document_requests_and_responses(self):
        paths = SchemaGenerator().get_schema(public=True)["paths"]
        for path, method, status in (
            ("/api/cart/items/", "post", "201"),
            ("/api/cart/items/{item_id}/", "patch", "200"),
            ("/api/users/me/top-up/", "post", "200"),
        ):
            operation = paths[path][method]
            self.assertIn("requestBody", operation)
            self.assertIn(status, operation["responses"])
        self.assertIn("201", paths["/api/orders/checkout/"]["post"]["responses"])
