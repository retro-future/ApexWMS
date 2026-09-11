"""Where a month starts and ends for one store — FR-10.8.

The tenant's timezone decides it, so a sale at 23:30 on the 31st in
Tashkent lands in that month rather than the next one. Both instants come
back in UTC, because that is what the two ledgers store.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from application.dtos import Period
from application.ports import TenantSettingsRepository


class PeriodResolver:
    def __init__(self, settings: TenantSettingsRepository) -> None:
        self._settings = settings

    async def today(self, now: datetime) -> date:
        """The store's own date, which a rate is quoted for (W9 B1).

        A rate entered at 01:00 UTC belongs to the day that is already
        under way in Tashkent, not to the one that ended there six hours
        ago.
        """
        zone = ZoneInfo(await self._settings.get_timezone())
        return now.astimezone(zone).date()

    async def month(self, year: int, month: int) -> Period:
        """``[00:00 on the 1st, 00:00 on the 1st of next month)``, local."""
        timezone = await self._settings.get_timezone()
        zone = ZoneInfo(timezone)
        start = datetime(year, month, 1, tzinfo=zone)
        end = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=zone)
        return Period(
            year=year,
            month=month,
            timezone=timezone,
            start=start.astimezone(UTC),
            end=end.astimezone(UTC),
        )
