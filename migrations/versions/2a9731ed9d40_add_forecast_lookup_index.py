"""add forecast lookup index

Revision ID: 2a9731ed9d40
Revises: 81fe5d2b22d6
Create Date: 2026-06-01 20:02:37.705866

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a9731ed9d40'
down_revision = '81fe5d2b22d6'
branch_labels = None
depends_on = None


def upgrade():
    # forecast 조회 가속용 부분 인덱스.
    # 기존 idx_weather_lookup 은 (base_date, base_time) 기준이라
    # _backfill_current_sky / _get_forecast_from_db 의 (fcst_date, fcst_time) 패턴과
    # 어긋난다. api_type='forecast' 행만 색인해서 인덱스 크기도 작게 유지.
    op.create_index(
        'idx_weather_forecast_fcst',
        'weather',
        ['nx', 'ny', 'fcst_date', 'fcst_time'],
        postgresql_where=sa.text("api_type = 'forecast'"),
    )


def downgrade():
    op.drop_index('idx_weather_forecast_fcst', table_name='weather')
