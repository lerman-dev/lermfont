from datetime import datetime
import asyncio
from .. import loader, utils
from herokutl.types import Message
from herokutl.tl.functions.account import UpdateProfileRequest


@loader.tds
class AutoNameChanger(loader.Module):
    """Автоматически меняет имя с текущим временем UTC+6"""
    strings = {"name": "AutoNameChanger"}

    def __init__(self):
        self.is_running = False
        self.task = None

    async def client_ready(self, client, db):
        self.client = client
        self._db = db
        
        # Проверяем, был ли запущен
        self.is_running = self._db.get("AutoNameChanger", "running", False)
        if self.is_running:
            await self._start_auto_change()

    def get_utc6_time(self):
        """Получаем время в формате UTC+6"""
        utc_now = datetime.utcnow()
        # Добавляем 6 часов для UTC+6
        utc6_hour = (utc_now.hour + 6) % 24
        return f"{utc6_hour:02d}:{utc_now.minute:02d}"

    async def change_name_now(self):
        """Меняет имя прямо сейчас"""
        try:
            time_str = self.get_utc6_time()
            new_name = f"Lerman | {time_str} | #KERNEL"
            
            # Используем UpdateProfileRequest как в примере
            await self.client(UpdateProfileRequest(
                first_name=new_name,
                last_name=""
            ))
            return True
        except Exception as e:
            # Если имя уже такое же, это не ошибка
            if "not modified" not in str(e).lower():
                print(f"AutoNameChanger error: {e}")
            return True

    async def _auto_change_loop(self):
        """Цикл автоматической смены имени"""
        while self.is_running:
            await self.change_name_now()
            await asyncio.sleep(60)  # Каждую минуту

    async def _start_auto_change(self):
        """Запускает автоматическую смену имени"""
        if self.task:
            try:
                self.task.cancel()
            except:
                pass
        
        self.is_running = True
        self._db.set("AutoNameChanger", "running", True)
        
        # Меняем сразу
        await self.change_name_now()
        
        # Запускаем цикл
        self.task = asyncio.create_task(self._auto_change_loop())

    async def _stop_auto_change(self):
        """Останавливает автоматическую смену имени"""
        self.is_running = False
        self._db.set("AutoNameChanger", "running", False)
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    @loader.command(
        ru_doc="Запустить автосмену имени"
    )
    async def startname(self, message: Message):
        """Запустить автосмену имени"""
        if self.is_running:
            try:
                await message.delete()
            except:
                pass
            return
        
        await self._start_auto_change()
        await utils.answer(message, "✅ Автосмена имени запущена!")
        await asyncio.sleep(2)
        await message.delete()

    @loader.command(
        ru_doc="Остановить автосмену имени"
    )
    async def stopname(self, message: Message):
        """Остановить автосмену имени"""
        if not self.is_running:
            try:
                await message.delete()
            except:
                pass
            return
        
        await self._stop_auto_change()
        await utils.answer(message, "❌ Автосмена имени остановлена!")
        await asyncio.sleep(2)
        await message.delete()

    @loader.command(
        ru_doc="Сменить имя один раз"
    )
    async def changename(self, message: Message):
        """Сменить имя один раз"""
        await self.change_name_now()
        time_str = self.get_utc6_time()
        await utils.answer(message, f"✅ Имя изменено на: Lerman | {time_str} | #KERNEL")
        await asyncio.sleep(2)
        await message.delete()

    @loader.command(
        ru_doc="Показать текущее время UTC+6"
    )
    async def showtime(self, message: Message):
        """Показать текущее время UTC+6"""
        time_str = self.get_utc6_time()
        await utils.answer(message, f"🕐 Текущее время UTC+6: {time_str}")
        await asyncio.sleep(2)
        await message.delete()

    async def on_unload(self):
        """При выгрузке модуля"""
        await self._stop_auto_change()
