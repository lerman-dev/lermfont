from datetime import datetime, timedelta
import pytz
from herokutl.types import Message
from .. import loader, utils


@loader.tds
class NameChangerModule(loader.Module):
    """Модуль для автоматического изменения имени пользователя с текущим временем"""
    strings = {
        "name": "NameChanger",
        "started": "✅ Автоматическая смена имени запущена!",
        "stopped": "❌ Автоматическая смена имени остановлена!",
        "status": "📊 Статус автоматической смены имени: {}",
        "format": "Lerman | {} | #KERNEL"
    }
    strings_ru = {
        "name": "СменаИмени",
        "started": "✅ Автоматическая смена имени запущена!",
        "stopped": "❌ Автоматическая смена имени остановлена!",
        "status": "📊 Статус автоматической смены имени: {}",
        "format": "Lerman | {} | #KERNEL"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "auto_start",
                False,
                "Автоматически запускать при загрузке",
                validator=loader.validators.Boolean()
            ),
            loader.ConfigValue(
                "timezone",
                "Asia/Almaty",  # UTC+6
                "Часовой пояс для отображения времени",
                validator=loader.validators.String()
            )
        )
        self.task = None

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        
        # Загружаем состояние из базы данных
        self.running = self.db.get("NameChanger", "running", False)
        
        # Автозапуск если включен в конфиге
        if self.config["auto_start"] and not self.running:
            await self.start_namechanger()
        elif self.running:
            await self.start_namechanger()

    def get_current_time(self):
        """Получаем текущее время в формате UTC+6"""
        try:
            # Создаем временную зону UTC+6
            tz = pytz.timezone(self.config["timezone"])
        except pytz.exceptions.UnknownTimeZoneError:
            # Если часовой пояс не найден, используем UTC+6 вручную
            tz = pytz.timezone('Etc/GMT-6')
        
        current_time = datetime.now(tz)
        return current_time.strftime("%H:%M")

    async def update_name(self):
        """Обновляет имя пользователя"""
        try:
            current_time = self.get_current_time()
            new_name = self.strings("format").format(current_time)
            
            await self.client(
                self.client.functions.account.UpdateProfile(
                    first_name=new_name
                )
            )
        except Exception as e:
            # Логируем ошибку, но не прерываем выполнение
            print(f"Ошибка при обновлении имени: {e}")

    async def start_namechanger(self):
        """Запускает автоматическую смену имени"""
        if self.task:
            self.task.cancel()
        
        # Обновляем сразу при запуске
        await self.update_name()
        
        # Запускаем периодическую задачу
        self.task = self.inline.task(lambda: self.update_name(), interval=60)
        self.running = True
        self.db.set("NameChanger", "running", True)

    async def stop_namechanger(self):
        """Останавливает автоматическую смену имени"""
        if self.task:
            self.task.cancel()
            self.task = None
        
        self.running = False
        self.db.set("NameChanger", "running", False)

    @loader.command(
        ru_doc="Запустить автоматическую смену имени",
        alias="startname"
    )
    async def startnamecmd(self, message: Message):
        """Запустить автоматическую смену имени"""
        await self.start_namechanger()
        await utils.answer(message, self.strings("started"))

    @loader.command(
        ru_doc="Остановить автоматическую смену имени",
        alias="stopname"
    )
    async def stopnamecmd(self, message: Message):
        """Остановить автоматическую смену имени"""
        await self.stop_namechanger()
        await utils.answer(message, self.strings("stopped"))

    @loader.command(
        ru_doc="Показать статус автоматической смены имени",
        alias="namestatus"
    )
    async def namestatuscmd(self, message: Message):
        """Показать статус автоматической смены имени"""
        status = "✅ Включена" if self.running else "❌ Выключена"
        await utils.answer(message, self.strings("status").format(status))

    @loader.command(
        ru_doc="Обновить имя вручную",
        alias="updatename"
    )
    async def updatenamecmd(self, message: Message):
        """Обновить имя вручную"""
        await self.update_name()
        await utils.answer(message, "✅ Имя обновлено вручную")

    @loader.command(
        ru_doc="Показать текущее время для формата имени",
        alias="showtime"
    )
    async def showtimecmd(self, message: Message):
        """Показать текущее время для формата имени"""
        current_time = self.get_current_time()
        formatted_name = self.strings("format").format(current_time)
        await utils.answer(message, f"🕐 Текущее время: {current_time}\n📝 Имя будет: {formatted_name}")

    @loader.watcher(only_pm=False, only_outgoing=False, only_messages=False)
    async def watcher(self, message: Message):
        """Вотчер для обработки команд в любом чате"""
        text = utils.get_args_raw(message)
        
        if text and text.lower() == "namestatus":
            await self.namestatuscmd(message)
        elif text and text.lower() == "startname":
            await self.startnamecmd(message)
        elif text and text.lower() == "stopname":
            await self.stopnamecmd(message)
        elif text and text.lower() == "updatename":
            await self.updatenamecmd(message)
        elif text and text.lower() == "showtime":
            await self.showtimecmd(message)
