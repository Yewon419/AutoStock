from sqlalchemy.orm import Session
from models.strategy import Strategy


def get_strategies(db: Session, user_id: int):
    return (
        db.query(Strategy)
        .filter(Strategy.user_id == user_id)
        .order_by(Strategy.created_at.desc())
        .all()
    )


def get_strategy(db: Session, strategy_id: int, user_id: int):
    return (
        db.query(Strategy)
        .filter(Strategy.id == strategy_id, Strategy.user_id == user_id)
        .first()
    )


def create_strategy(db: Session, user_id: int, name: str, description, conditions: list):
    strategy = Strategy(user_id=user_id, name=name, description=description, conditions=conditions)
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


def update_strategy(db: Session, strategy_id: int, user_id: int, data: dict):
    strategy = get_strategy(db, strategy_id, user_id)
    if not strategy:
        return None
    for k, v in data.items():
        setattr(strategy, k, v)
    db.commit()
    db.refresh(strategy)
    return strategy


def delete_strategy(db: Session, strategy_id: int, user_id: int) -> bool:
    strategy = get_strategy(db, strategy_id, user_id)
    if not strategy:
        return False
    db.delete(strategy)
    db.commit()
    return True
