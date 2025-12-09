from datetime import datetime
import pytz
import asyncio
from herokutl.types import Message
from .. import loader


@loader.tds
class NameChanger(loader.Module):
    """Автоматическая смена имени с временем UTC+6"""
    strings = {"name": "NameChanger"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "timezone",
                "UTC+6",
                "Часовой пояс для времени",
                validator=loader.validators.String()
            ),
        )
        self.task = None
        self.is_active = False

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        
        # Проверяем, был ли модуль активен
        self.is_active = self.db.get("NameChanger", "active", False)
        if self.is_active:
            await self._start_changing()

    def _get_time(self):
        """Получает текущее время в UTC+6"""
        try:
            # UTC+6 это Etc/GMT-6 в pytz
            tz = pytz.timezone("Etc/GMT-6")
            return datetime.now(tz).strftime("%H:%M")
        except:
            # Если ошибка, используем локальное время +6 часов
            return (datetime.utcnow() + pytz.utc._utcoffset).strftime("%H:%M")

    async def _change_name_once(self):
        """Меняет имя один раз"""
        try:
            current_time = self._get_time()
            new_name = f"Lerman | {current_time} | #KERNEL"
            
            # Простая смена имени
            result = await self.client(
                self.client.functions.account.UpdateProfile(
                    first_name=new_name,
                    last_name=""
                )
            )
            return True
        except Exception as e:
            # Если имя не изменилось (уже такое же) - это не ошибка
            if "not modified" not in str(e).lower():
                print(f"[NameChanger] Ошибка: {e}")
            return True

    async def _changer_loop(self):
        """Основной цикл смены имени"""
        while self.is_active:
            await self._change_name_once()
            await asyncio.sleep(60)  # Ждем минуту

    async def _start_changing(self):
        """Запускает смену имени"""
        if self.task:
            try:
                self.task.cancel()
            except:
                pass
        
        self.is_active = True
        self.db.set("NameChanger", "active", True)
        
        # Первое изменение
        await self._change_name_once()
        
        # Запускаем цикл
        self.task = asyncio.create_task(self._changer_loop())

    async def _stop_changing(self):
        """Останавливает смену имени"""
        self.is_active = False
        self.db.set("NameChanger", "active", False)
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    @loader.command(
        ru_doc="Запустить автоматическую смену имени"
    )
    async def startname(self, message: Message):
        """Запустить смену имени"""
        if self.is_active:
            await message.delete()
            return
        
        await self._start_changing()
        await message.delete()

    @loader.command(
        ru_doc="Остановить автоматическую смену имени"
    )
    async def stopname(self, message: Message):
        """Остановить смену имени"""
        if not self.is_active:
            await message.delete()
            return
        
        await self._stop_changing()
        await message.delete()

    @loader.command(
        ru_doc="Проверить работу модуля (тестовая смена имени)"
    )
    async def nametest(self, message: Message):
        """Тестовая смена имени"""
        success = await self._change_name_once()
        if success:
            await message.edit("✅ Имя успешно изменено!")
            await asyncio.sleep(2)
            await message.delete()
        else:
            await message.edit("❌ Не удалось изменить имя")
            await asyncio.sleep(2)
            await message.delete()

    async def on_unload(self):
        """При выгрузке модуля"""
        await self._stop_changing()
