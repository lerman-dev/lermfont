import asyncio
from datetime import datetime
from .. import loader
from herokutl.types import Message


@loader.tds
class NameUpdater(loader.Module):
    """Обновляет имя с временем UTC+6"""
    strings = {"name": "NameUpdater"}

    def __init__(self):
        self.active = False
        self.task = None

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        if self.db.get("NameUpdater", "active", False):
            self.active = True
            self.task = asyncio.create_task(self.update_loop())

    async def update_name(self):
        """Обновляет имя"""
        try:
            # Простое вычисление UTC+6
            utc_hour = datetime.utcnow().hour
            minute = datetime.utcnow().minute
            utc6_hour = (utc_hour + 6) % 24
            
            new_name = f"Lerman | {utc6_hour:02d}:{minute:02d} | #KERNEL"
            
            # Прямой вызов API
            from herokutl import functions
            await self.client(functions.account.UpdateProfile(
                first_name=new_name
            ))
        except:
            pass  # Игнорируем все ошибки

    async def update_loop(self):
        """Цикл обновления"""
        while self.active:
            await self.update_name()
            await asyncio.sleep(60)

    @loader.command()
    async def startname(self, message: Message):
        """Включить автообновление имени"""
        if not self.active:
            self.active = True
            self.db.set("NameUpdater", "active", True)
            self.task = asyncio.create_task(self.update_loop())
            await self.update_name()  # Сразу меняем
        await message.delete()

    @loader.command()
    async def stopname(self, message: Message):
        """Выключить автообновление имени"""
        if self.active:
            self.active = False
            self.db.set("NameUpdater", "active", False)
            if self.task:
                self.task.cancel()
        await message.delete()

    async def on_unload(self):
        if self.task:
            self.task.cancel()
