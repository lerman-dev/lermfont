from datetime import datetime, timedelta
import pytz
from herokutl.types import Message
from .. import loader, utils


@loader.tds
class NameChangerModule(loader.Module):
    """Модуль для автоматического изменения имени пользователя с текущим временем"""
    strings = {
        "name": "NameChanger",
        "started": "✅ Автоматическая смена имени запущена!\nЧасовой пояс: {}",
        "stopped": "❌ Автоматическая смена имени остановлена!",
        "status": "📊 Статус автоматической смены имени: {}\nЧасовой пояс: {}\nСледующее обновление: {}",
        "format": "Lerman | {} | #KERNEL",
        "timezone_set": "✅ Часовой пояс установлен на: {}\nТекущее время: {}",
        "invalid_timezone": "❌ Неверный часовой пояс! Примеры правильных форматов:\n"
                          "• <code>Asia/Almaty</code> (UTC+6)\n"
                          "• <code>Europe/Moscow</code> (UTC+3)\n"
                          "• <code>UTC+6</code>\n"
                          "• <code>Etc/GMT-6</code>\n\n"
                          "Список всех зон: https://gist.github.com/heyalexej/8bf688fd67d7199be4a1682b3eec7568",
        "current_timezone": "📍 Текущий часовой пояс: {}\n🕐 Текущее время: {}",
        "timezone_list": "🌍 Популярные часовые пояса:\n"
                        "• <code>Asia/Almaty</code> - UTC+6 (Казахстан)\n"
                        "• <code>Europe/Moscow</code> - UTC+3 (Москва)\n"
                        "• <code>Europe/London</code> - UTC+0 (Лондон)\n"
                        "• <code>Asia/Tokyo</code> - UTC+9 (Токио)\n"
                        "• <code>America/New_York</code> - UTC-5 (Нью-Йорк)\n"
                        "• <code>UTC+6</code> - Прямое указание смещения\n"
                        "• <code>Etc/GMT-6</code> - Альтернативный формат UTC+6",
        "next_update_in": "Следующее обновление через: {} секунд"
    }
    strings_ru = {
        "name": "СменаИмени",
        "started": "✅ Автоматическая смена имени запущена!\nЧасовой пояс: {}",
        "stopped": "❌ Автоматическая смена имени остановлена!",
        "status": "📊 Статус автоматической смены имени: {}\nЧасовой пояс: {}\nСледующее обновление: {}",
        "format": "Lerman | {} | #KERNEL",
        "timezone_set": "✅ Часовой пояс установлен на: {}\nТекущее время: {}",
        "invalid_timezone": "❌ Неверный часовой пояс! Примеры правильных форматов:\n"
                          "• <code>Asia/Almaty</code> (UTC+6)\n"
                          "• <code>Europe/Moscow</code> (UTC+3)\n"
                          "• <code>UTC+6</code>\n"
                          "• <code>Etc/GMT-6</code>\n\n"
                          "Список всех зон: https://gist.github.com/heyalexej/8bf688fd67d7199be4a1682b3eec7568",
        "current_timezone": "📍 Текущий часовой пояс: {}\n🕐 Текущее время: {}",
        "timezone_list": "🌍 Популярные часовые пояса:\n"
                        "• <code>Asia/Almaty</code> - UTC+6 (Казахстан)\n"
                        "• <code>Europe/Moscow</code> - UTC+3 (Москва)\n"
                        "• <code>Europe/London</code> - UTC+0 (Лондон)\n"
                        "• <code>Asia/Tokyo</code> - UTC+9 (Токио)\n"
                        "• <code>America/New_York</code> - UTC-5 (Нью-Йорк)\n"
                        "• <code>UTC+6</code> - Прямое указание смещения\n"
                        "• <code>Etc/GMT-6</code> - Альтернативный формат UTC+6",
        "next_update_in": "Следующее обновление через: {} секунд"
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
                "Asia/Almaty",
                "Часовой пояс для отображения времени",
                validator=loader.validators.String()
            ),
            loader.ConfigValue(
                "update_interval",
                60,
                "Интервал обновления в секундах",
                validator=loader.validators.Integer(minimum=10, maximum=3600)
            )
        )
        self.task = None
        self.last_update = None
        self.next_update = None

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

    def validate_timezone(self, timezone_str):
        """Проверяет валидность часового пояса"""
        try:
            # Пытаемся создать временную зону
            if timezone_str.startswith("UTC"):
                # Преобразуем UTC+6 в Etc/GMT-6
                offset = timezone_str[3:]  # Получаем "+6" или "-5"
                if offset.startswith("+"):
                    gmt_offset = f"Etc/GMT-{offset[1:]}"  # pytz использует обратную логику
                elif offset.startswith("-"):
                    gmt_offset = f"Etc/GMT{offset}"  # pytz использует обратную логику
                else:
                    gmt_offset = f"Etc/GMT{offset}"
                pytz.timezone(gmt_offset)
                return gmt_offset
            else:
                pytz.timezone(timezone_str)
                return timezone_str
        except:
            # Если не удалось, пробуем Etc/GMT формат
            try:
                if not timezone_str.startswith("Etc/GMT"):
                    # Пробуем добавить Etc/GMT
                    if "+" in timezone_str or "-" in timezone_str:
                        if timezone_str.startswith("UTC"):
                            offset = timezone_str[3:]
                            if offset.startswith("+"):
                                gmt_offset = f"Etc/GMT-{offset[1:]}"
                            elif offset.startswith("-"):
                                gmt_offset = f"Etc/GMT{offset}"
                            else:
                                gmt_offset = f"Etc/GMT{offset}"
                            pytz.timezone(gmt_offset)
                            return gmt_offset
                else:
                    pytz.timezone(timezone_str)
                    return timezone_str
            except:
                return None

    def get_current_time(self):
        """Получаем текущее время в установленном часовом поясе"""
        try:
            timezone_str = self.config["timezone"]
            tz = pytz.timezone(timezone_str)
            current_time = datetime.now(tz)
            return current_time.strftime("%H:%M"), current_time.strftime("%H:%M:%S")
        except Exception as e:
            # Если часовой пояс невалидный, используем UTC+6 по умолчанию
            try:
                tz = pytz.timezone("Asia/Almaty")
                current_time = datetime.now(tz)
                return current_time.strftime("%H:%M"), current_time.strftime("%H:%M:%S")
            except:
                # В крайнем случае используем локальное время
                current_time = datetime.now()
                return current_time.strftime("%H:%M"), current_time.strftime("%H:%M:%S")

    async def update_name(self):
        """Обновляет имя пользователя"""
        try:
            current_time, full_time = self.get_current_time()
            new_name = self.strings("format").format(current_time)
            
            await self.client(
                self.client.functions.account.UpdateProfile(
                    first_name=new_name
                )
            )
            
            self.last_update = datetime.now()
            self.next_update = self.last_update + timedelta(seconds=self.config["update_interval"])
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
        self.task = self.inline.task(
            lambda: self.update_name(), 
            interval=self.config["update_interval"]
        )
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
        timezone = self.config["timezone"]
        await utils.answer(message, self.strings("started").format(timezone))

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
        timezone = self.config["timezone"]
        
        # Получаем текущее время для отображения
        current_time, full_time = self.get_current_time()
        
        # Рассчитываем время до следующего обновления
        next_update_str = "Неизвестно"
        if self.running and self.next_update:
            now = datetime.now()
            if self.next_update > now:
                seconds_left = (self.next_update - now).seconds
                next_update_str = f"{seconds_left}с"
            else:
                next_update_str = "Скоро"
        
        await utils.answer(
            message, 
            self.strings("status").format(status, timezone, next_update_str)
        )

    @loader.command(
        ru_doc="Установить часовой пояс (пример: .settimezone Asia/Almaty)",
        alias="settimezone"
    )
    async def settimezonecmd(self, message: Message):
        """Установить часовой пояс"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, "❌ Укажите часовой пояс!\nПример: <code>.settimezone Asia/Almaty</code>")
            return
        
        validated_tz = self.validate_timezone(args)
        if validated_tz:
            self.config["timezone"] = validated_tz
            current_time, full_time = self.get_current_time()
            await utils.answer(
                message, 
                self.strings("timezone_set").format(validated_tz, full_time)
            )
            
            # Если смена имени запущена, обновляем сразу
            if self.running:
                await self.update_name()
        else:
            await utils.answer(message, self.strings("invalid_timezone"))

    @loader.command(
        ru_doc="Показать текущий часовой пояс",
        alias="timezone"
    )
    async def timezonecmd(self, message: Message):
        """Показать текущий часовой пояс"""
        timezone = self.config["timezone"]
        current_time, full_time = self.get_current_time()
        await utils.answer(
            message, 
            self.strings("current_timezone").format(timezone, full_time)
        )

    @loader.command(
        ru_doc="Список популярных часовых поясов",
        alias="timezones"
    )
    async def timezonescmd(self, message: Message):
        """Список популярных часовых поясов"""
        await utils.answer(message, self.strings("timezone_list"))

    @loader.command(
        ru_doc="Обновить имя вручную",
        alias="updatename"
    )
    async def updatenamecmd(self, message: Message):
        """Обновить имя вручную"""
        await self.update_name()
        current_time, full_time = self.get_current_time()
        await utils.answer(message, f"✅ Имя обновлено вручную\n🕐 Время: {full_time}")

    @loader.command(
        ru_doc="Показать текущее время для формата имени",
        alias="showtime"
    )
    async def showtimecmd(self, message: Message):
        """Показать текущее время для формата имени"""
        current_time, full_time = self.get_current_time()
        formatted_name = self.strings("format").format(current_time)
        await utils.answer(
            message, 
            f"📍 Часовой пояс: {self.config['timezone']}\n"
            f"🕐 Текущее время: {full_time}\n"
            f"📝 Имя будет: {formatted_name}"
        )

    @loader.command(
        ru_doc="Установить интервал обновления в секундах (мин. 10, макс. 3600)",
        alias="setinterval"
    )
    async def setintervalcmd(self, message: Message):
        """Установить интервал обновления"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(
                message, 
                f"❌ Укажите интервал в секундах!\n"
                f"Текущий интервал: {self.config['update_interval']} секунд\n"
                f"Пример: <code>.setinterval 30</code>"
            )
            return
        
        try:
            interval = int(args)
            if interval < 10 or interval > 3600:
                await utils.answer(
                    message, 
                    f"❌ Интервал должен быть от 10 до 3600 секунд!\n"
                    f"Текущий интервал: {self.config['update_interval']} секунд"
                )
                return
            
            old_interval = self.config['update_interval']
            self.config['update_interval'] = interval
            
            # Перезапускаем задачу если она запущена
            if self.running:
                await self.stop_namechanger()
                await self.start_namechanger()
            
            await utils.answer(
                message, 
                f"✅ Интервал обновления изменен:\n"
                f"Старый: {old_interval} секунд\n"
                f"Новый: {interval} секунд"
            )
        except ValueError:
            await utils.answer(message, "❌ Интервал должен быть числом!")

    @loader.watcher(only_pm=False, only_outgoing=False, only_messages=False)
    async def watcher(self, message: Message):
        """Вотчер для обработки команд в любом чате"""
        text = utils.get_args_raw(message)
        
        if text:
            text_lower = text.lower()
            if text_lower == "namestatus":
                await self.namestatuscmd(message)
            elif text_lower == "startname":
                await self.startnamecmd(message)
            elif text_lower == "stopname":
                await self.stopnamecmd(message)
            elif text_lower == "updatename":
                await self.updatenamecmd(message)
            elif text_lower == "showtime":
                await self.showtimecmd(message)
            elif text_lower == "timezone":
                await self.timezonecmd(message)
            elif text_lower == "timezones":
                await self.timezonescmd(message)
            elif text_lower.startswith("settimezone"):
                await self.settimezonecmd(message)
            elif text_lower.startswith("setinterval"):
                await self.setintervalcmd(message)
