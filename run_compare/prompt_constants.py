from typing import TypedDict, get_type_hints, _GenericAlias, get_origin, get_args


def typed_dict_to_json_schema(typed_dict_class):
    """Converts a TypedDict class to a JSON schema.

    Args:
        typed_dict_class: The TypedDict class to convert.

    Returns:
        A dictionary representing the JSON schema.
    """

    schema = {
        "type": "object",
        "properties": {},
        "required": []
    }
    if hasattr(typed_dict_class, "descriptions"):
        descriptions = typed_dict_class.descriptions
    else:
        descriptions = {}
    type_hints = get_type_hints(typed_dict_class)

    for key, value_type in type_hints.items():
        property_schema = _get_property_schema(value_type, descriptions.get(key))

        # Add description if available
        # if hasattr(typed_dict_class, "descriptions") and key in typed_dict_class.descriptions:
        #     property_schema["description"] = typed_dict_class.descriptions[key]

        schema["properties"][key] = property_schema
        if key in typed_dict_class.__annotations__:
            schema["required"].append(key)

    return schema

def _get_property_schema(python_type, description=None):
    """Maps Python types to JSON Schema types."""
    if isinstance(python_type, _GenericAlias):
        origin = python_type.__origin__
        if origin is list:
            return {'type': "array",
                    'items': _get_property_schema(get_args(python_type)[0]),
                    'description': description
                    }
        elif origin is dict:
            return {'type': "object",
                    'properties': {k: _get_property_schema(v) for k, v in get_type_hints(get_args(python_type)[0]).items()},
                    'description': description
                    }
    elif python_type == str:
        return {'type': "string",
                'description': description}
    elif python_type == int:
        return {'type': "integer",
                'description': description}
    elif python_type == float:
        return {'type': "number",
                'description': description}
    elif python_type == bool:
        return {'type': "boolean",
                'description': description}
    # elif getattr(python_type, "__origin__", None) is dict:
    #     return "object"
    elif getattr(python_type, "__origin__", None) is list:
        return {'type': "array",
                'items': _get_property_schema(python_type.__args__[0])            ,
                'description': description}

    elif isinstance(python_type, type):# and issubclass(python_type, TypedDict):
        return typed_dict_to_json_schema(python_type)
    else:
        return "string"  # Default to string for unknown types

class Exercise(TypedDict):
    distance: float
    target_pace: float
    target_heart_rate: int
    repetitions: int
    rest_time: float
    descriptions = {'distance': 'The exercise distance in meters',
                    'target_pace': 'The target running pace in minutes per kilometer',
                    'target_heart_rate': 'The target heart rate in beats per minute',
                    'repetitions': 'The number of repetitions if is an interval workout otherwise 1',
                    'rest_time': 'The rest time between repetitions in minutes',
                    }

class RUN(TypedDict):
    type: str
    plan: list[Exercise]
    descriptions = {'type': 'The type of run (base or interval)',
                    'plan': 'The list of exercises to perform'
                    }

class AI_SCHEMA_TYPE(TypedDict):
    progress: str
    next_suggested_run: RUN
    descriptions = {'progress': 'The current progress of the athlete',
                    'next_suggested_run': 'The next suggested run based on the athlete progress'
                    }

exercise_json = typed_dict_to_json_schema(Exercise)
run_json = typed_dict_to_json_schema(RUN)
ai_schema_type_json = typed_dict_to_json_schema(AI_SCHEMA_TYPE)

SUGGESTED_EXERCISE_PROMPT = '''Here are the past exercises of a runner. Based on the runs and there results (pace, heart rate, etc.)
                             assess the runners progress and suggest the next exercise''' #. The runner can either do a base run or an interval run.'''
SYSTEM_PROMPT = ''' You are a personal trainer for a runner. The runner aims to run 10K races'''