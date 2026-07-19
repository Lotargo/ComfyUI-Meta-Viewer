from __future__ import annotations

from . import intent_benchmark_core as _core
from .intent_benchmark_core import *  # noqa: F401,F403
from .intent_benchmark_policy import strict_intent_status

# Keep the CLI and tests on one conservative status policy without coupling the
# large benchmark core to the policy implementation.
_core.intent_status = strict_intent_status
intent_status = strict_intent_status
main = _core.main


if __name__ == "__main__":
    raise SystemExit(main())
