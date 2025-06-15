from adaptivecad.ai import openai_bridge, translator


def test_sine_surface_roundtrip(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")

    def fake_call(_prompt: str, model: str | None = None):
        return {
            "kind": "solid",
            "primitive": "extrude",
            "parameters": {
                "profile": {
                    "kind": "surface",
                    "primitive": "implicit",
                    "parameters": {
                        "equation": "z - sin(x)*cos(y)",
                        "domain": {"x": [-3.1416, 3.1416], "y": [-3.1416, 3.1416]},
                    },
                },
                "height": 15.0,
            },
        }

    monkeypatch.setattr(openai_bridge, "call_openai", fake_call)
    spec = openai_bridge.call_openai("dummy")
    geom = translator.build_geometry(spec)
    assert geom.is_manifold()
