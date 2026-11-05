"""Gli schemi mandati all'API non devono contenere le parole che l'API rifiuta (errore 400 visto sul Mac il 5/11)."""
import json

from firm import meetings, workflows
from llm import providers

FORBIDDEN = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "minLength", "maxLength",
             "maxItems", "uniqueItems"}


def _keys(node, acc):
    if isinstance(node, dict):
        acc.update(node)
        for v in node.values():
            _keys(v, acc)
    elif isinstance(node, list):
        for v in node:
            _keys(v, acc)
    return acc


def test_every_schema_is_api_safe():
    schemas = [v for mod in (workflows, meetings) for k, v in vars(mod).items()
               if isinstance(v, dict) and v.get("type") == "object" and k.isupper()]
    assert schemas
    for sch in schemas:
        assert not (_keys(providers.api_schema(sch), set()) & FORBIDDEN)


def test_original_schema_is_untouched_and_still_validates():
    import jsonschema
    sch = {"type": "object", "properties": {"p": {"type": "number", "minimum": 0, "maximum": 1}}, "required": ["p"]}
    safe = providers.api_schema(sch)
    assert "minimum" in json.dumps(sch) and "minimum" not in json.dumps(safe)
    jsonschema.validate({"p": 0.5}, sch)
    try:
        jsonschema.validate({"p": 7}, sch)
        assert False
    except jsonschema.ValidationError:
        pass
