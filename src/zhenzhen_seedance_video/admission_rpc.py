"""Bounded intake RPC surface. No caller-supplied verification evidence."""

from .admission import AdmissionError
from .materials import MaterialError
from .parameters import ParameterError
from .storage import StorageError
from .task_state import StateError
from .windows_security import SecurityError


def handlers(service):
    async def submit_video(request_key, request, allow_once=False):
        return await service.submit(request_key, request, allow_once=allow_once)

    async def upscale_video(request_key, request):
        return await service.submit(request_key, request, api_id="zhenzhen-upscaler")

    def bounded(function):
        async def call(params):
            try:
                return await function(**params)
            except ParameterError as error:
                return {"ok": False, "error": error.code, "field": error.field_name}
            except (
                AdmissionError,
                MaterialError,
                StorageError,
                StateError,
                SecurityError,
            ) as error:
                result = {"ok": False, "error": str(error)}
                if isinstance(error, StateError) and error.snapshot:
                    result["task"] = error.snapshot
                return result
            except (ValueError, TypeError):
                return {"ok": False, "error": "INVALID_TOOL_INPUT"}
            except OSError:
                return {"ok": False, "error": "LOCAL_FILE_OPERATION_FAILED"}

        return call

    return {
        name: bounded(function)
        for name, function in {
            "submit_video": submit_video,
            "upscale_video": upscale_video,
            "find_task_by_request_key": service.find,
            "get_prompt_optimization_policy": service.get_preference,
            "set_prompt_optimization_policy": service.set_preference,
            "repair_task_materials": service.repair,
        }.items()
    }
