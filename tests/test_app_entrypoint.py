import unittest


class AppEntrypointTests(unittest.TestCase):
    def test_ingest_route_is_registered_once(self) -> None:
        import app

        routes = [
            route for route in app.app.routes
            if getattr(route, "path", None) == "/api/v1/ingest/events"
            and "POST" in getattr(route, "methods", set())
        ]
        self.assertEqual(len(routes), 1)
        self.assertIs(routes[0].endpoint, app.ingest_event)

    def test_all_existing_api_routes_remain_available(self) -> None:
        import app

        paths = {getattr(route, "path", None) for route in app.app.routes}
        self.assertIn("/health", paths)
        self.assertIn("/api/v1/entities", paths)
        self.assertIn("/api/v1/tasks", paths)
        self.assertIn("/api/v1/recommendations", paths)
        self.assertIn("/api/v1/entities/stream", paths)


if __name__ == "__main__":
    unittest.main()
