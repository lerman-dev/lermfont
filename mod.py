from datetime import datetime
import pytz
import asyncio
from herokutl.types import Message
from .. import loader, utils


@loader.tds
class NameChangerModule(loader.Module):
    """Модуль для автоматического изменения имени пользователя"""
    strings = {"name": "NameChanger"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "timezone",
                "UTC+6",
                "Часовой пояс",
                validator=loader.validators.String()
            ),
        )
        self.task = None
        self.running = False

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.running = self.db.get("NameChanger", "running", False)
        
        # Если был запущен, запускаем снова
        if self.running:
            await self.start_namechanger()

    def get_timezone(self):
        """Получаем объект часового пояса"""
        try:
            if self.config["timezone"].upper().startswith("UTC"):
                tz_str = self.config["timezone"].upper()
                offset = tz_str[3:]
                if offset.startswith("+"):
                    return pytz.timezone(f"Etc/GMT-{offset[1:]}")
                elif offset.startswith("-"):
                    return pytz.timezone(f"Etc/GMT{offset}")
                else:
                    return pytz.timezone(f"Etc/GMT-{offset}")
            else:
                return pytz.timezone(self.config["timezone"])
        except:
            return pytz.timezone("Etc/GMT-6")  # UTC+6 по умолчанию

    async def update_name(self):
        """Обновляет имя пользователя"""
        try:
            tz = self.get_timezone()
            current_time = datetime.now(tz).strftime("%H:%M")
            new_name = f"Lerman | {current_time} | #KERNEL"
            
            # Просто меняем имя без проверок
            await self.client(
                self.client.functions.account.UpdateProfile(
                    first_name=new_name
                )
            )
            return True
        except Exception as e:
            # Игнорируем ошибку "не изменилось"
            if "not modified" not in str(e).lower():
                print(f"Ошибка обновления имени: {e}")
            return True  # Все равно продолжаем

    async def namechanger_loop(self):
        """Цикл обновления имени"""
        while self.running:
            await self.update_name()
            await asyncio.sleep(60)  # Каждую минуту

    async def start_namechanger(self):
        """Запускает смену имени"""
        if self.task:
            self.task.cancel()
        
        self.running = True
        self.db.set("NameChanger", "running", True)
        
        # Обновляем сразу
        await self.update_name()
        
        # Запускаем цикл
        self.task = asyncio.create_task(self.namechanger_loop())
        return True

    async def stop_namechanger(self):
        """Останавливает смену имени"""
        self.running = False
        self.db.set("NameChanger", "running", False)
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except:
                pass
            self.task = None

    @loader.command(
        ru_doc="Запустить смену имени",
        alias="startname"
    )
    async def startnamecmd(self, message: Message):
        """Запустить смену имени"""
        if self.running:
            try:
                await message.delete()
            except:
                pass
            return
        
        await self.start_namechanger()
        
        # Просто удаляем сообщение команды
        try:
            await message.delete()
        except:
            pass

    @loader.command(
        ru_doc="Остановить смену имени",
        alias="stopname"
    )
    async def stopnamecmd(self, message: Message):
        """Остановить смену имени"""
        if not self.running:
            try:
                await message.delete()
            except:
                pass
            return
        
        await self.stop_namechanger()
        
        # Просто удаляем сообщение команды
        try:
            await message.delete()
        except:
            pass

    async def on_unload(self):
        """При выгрузке модуля"""
        await self.stop_namechanger()
