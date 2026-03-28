#!/usr/bin/env python3
"""
Seed roles and internal test questions. Run from repo root:

PYTHONPATH=apps/api/src python scripts/seed.py
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api", "src"))

from sqlalchemy import select

from invision_api.db.session import SessionLocal
from invision_api.models.application import InternalTestQuestion
from invision_api.models.enums import QuestionCategory, QuestionType, RoleName
from invision_api.repositories.role_repository import ensure_role


def seed_roles() -> None:
    db = SessionLocal()
    try:
        ensure_role(db, RoleName.candidate)
        ensure_role(db, RoleName.committee)
        ensure_role(db, RoleName.admin)
        db.commit()
        print("Roles ensured.")
    finally:
        db.close()


def seed_questions() -> None:
    db = SessionLocal()
    try:
        existing = db.scalars(select(InternalTestQuestion).limit(1)).first()
        if existing:
            print("Questions already present; skipping.")
            return

        items: list[InternalTestQuestion] = [
            InternalTestQuestion(
                category=QuestionCategory.logical_reasoning.value,
                question_type=QuestionType.single_choice.value,
                prompt="Если все «блупы» — это «раззи», а некоторые «раззи» — «лаззи», какое утверждение обязательно верно?",
                options=[
                    {"id": "a", "label": "Все «блупы» — «лаззи»"},
                    {"id": "b", "label": "Некоторые «блупы» могут быть «лаззи»"},
                    {"id": "c", "label": "Ни один «блуп» не является «лаззи»"},
                ],
                display_order=10,
                is_active=True,
                version=1,
            ),
            InternalTestQuestion(
                category=QuestionCategory.situational_judgement.value,
                question_type=QuestionType.text.value,
                prompt="Опишите ситуацию, когда вы разрешили конфликт в команде. Каков был результат?",
                options=None,
                display_order=20,
                is_active=True,
                version=1,
            ),
            InternalTestQuestion(
                category=QuestionCategory.self_reflection.value,
                question_type=QuestionType.multi_choice.value,
                prompt="Какие навыки вы хотите развить в процессе обучения? (выберите все подходящие)",
                options=[
                    {"id": "a", "label": "Письменная речь"},
                    {"id": "b", "label": "Публичные выступления"},
                    {"id": "c", "label": "Количественные рассуждения"},
                ],
                display_order=30,
                is_active=True,
                version=1,
            ),
            InternalTestQuestion(
                category=QuestionCategory.leadership_scenarios.value,
                question_type=QuestionType.text.value,
                prompt="Вы получаете проблемный проект со сроком сдачи через 3 недели. Каков ваш план на первую неделю?",
                options=None,
                display_order=40,
                is_active=True,
                version=1,
            ),
        ]
        for q in items:
            db.add(q)
        db.commit()
        print(f"Inserted {len(items)} internal test questions.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_roles()
    seed_questions()
