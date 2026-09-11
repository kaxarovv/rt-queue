"""
Единая точка, где импортируются ВСЕ ORM-модели проекта.

Модели в разных доменах ссылаются друг на друга через строковые
аннотации (Mapped["TreatmentCase"]), чтобы избежать циклических импортов
между domains/patients, domains/treatment_cases, domains/scheduling
и domains/documents. SQLAlchemy резолвит эти строки в реальные классы
только когда все они зарегистрированы в общем Base.metadata — это и
происходит здесь.

Этот модуль импортируется один раз при старте приложения (main.py)
и в env.py Alembic — до любых операций с БД.
"""

from app.domains.documents.models import SourceDocument  # noqa: F401
from app.domains.patients.models import Patient  # noqa: F401
from app.domains.scheduling.models import MachineSlot, Session  # noqa: F401
from app.domains.treatment_cases.models import TreatmentCase  # noqa: F401
