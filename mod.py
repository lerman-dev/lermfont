from datetime import datetime, timedelta
import pytz
import asyncio
from herokutl.types import Message
from .. import loader, utils


@loader.tds
class NameChangerModule(loader.Module):
    """Модуль для автоматического изменения имени пользователя с текущим временем"""
    strings = {
        "name": "NameChanger",
        "started": "✅ Автоматическая смена имени запущена!\nЧасовой пояс: {}\nИнтервал: {} секунд",
        "stopped": "❌ Автоматическая смена имени остановлена!",
        "status": "📊 Статус автоматической смены имени: {}\nЧасовой пояс: {}\nИнтервал: {} секунд\nПоследнее обновление: {}\nСледующее обновление: {}",
        "format": "Lerman | {} | #KERNEL",
        "timezone_set": "✅ Часовой пояс установлен на: {}\nТекущее время: {}",
        "invalid_timezone": "❌ Неверный часовой пояс! Примеры правильных форматов:\n"
                          "• <code>UTC+6</code> (рекомендуется)\n"
                          "• <code>Asia/Dhaka</code> (Дакка, Бангладеш)\n"
                          "• <code>Etc/GMT-6</code>\n\n"
                          "Для UTC+6 используйте: <code>UTC+6</code>",
        "current_timezone": "📍 Текущий часовой пояс: {}\n🕐 Текущее время: {}",
        "timezone_list": "🌍 Популярные часовые пояса UTC+6:\n"
                        "• <code>UTC+6</code> - UTC+6 (рекомендуется)\n"
                        "• <code>Asia/Dhaka</code> - Дакка, Бангладеш\n"
                        "• <code>Asia/Almaty</code> - Алматы, Казахстан\n"
                        "• <code>Asia/Bishkek</code> - Бишкек, Кыргызстан\n"
                        "• <code>Asia/Omsk</code> - Омск, Россия\n"
                        "• <code>Etc/GMT-6</code> - Альтернативный формат UTC+6",
        "interval_set": "✅ Интервал обновления установлен: {} секунд",
        "no_change": "⚠️ Имя не изменилось (уже установлено такое же значение)",
        "test_name": "✅ Тестовое имя установлено: {}"
    }
    strings_ru = {
        "name": "СменаИмени",
        "started": "✅ Автоматическая смена имени запущена!\nЧасовой пояс: {}\nИнтервал: {} секунд",
        "stopped": "❌ Автоматическая смена имени остановлена!",
        "status": "📊 Статус автоматической смены имени: {}\nЧасовой пояс: {}\nИнтервал: {} секунд\nПоследнее обновление: {}\nСледующее обновление: {}",
        "format": "Lerman | {} | #KERNEL",
        "timezone_set": "✅ Часовой пояс установлен на: {}\nТекущее время: {}",
        "invalid_timezone": "❌ Неверный часовой пояс! Примеры правильных форматов:\n"
                          "• <code>UTC+6</code> (рекомендуется)\n"
                          "• <code>Asia/Dhaka</code> (Дакка, Бангладеш)\n"
                          "• <code>Etc/GMT-6</code>\n\n"
                          "Для UTC+6 используйте: <code>UTC+6</code>",
        "current_timezone": "📍 Текущий часовой пояс: {}\n🕐 Текущее время: {}",
        "timezone_list": "🌍 Популярные часовые пояса UTC+6:\n"
                        "• <code>UTC+6</code> - UTC+6 (рекомендуется)\n"
                        "• <code>Asia/Dhaka</code> - Дакка, Бангладеш\n"
                        "• <code>Asia/Almaty</code> - Алматы, Казахстан\n"
                        "• <code>Asia/Bishkek</code> - Бишкек, Кыргызстан\n"
                        "• <code>Asia/Omsk</code> - Омск, Россия\n"
                        "• <code>Etc/GMT-6</code> - Альтернативный формат UTC+6",
        "interval_set": "✅ Интервал обновления установлен: {} секунд",
        "no_change": "⚠️ Имя не изменилось (уже установлено такое же значение)",
        "test_name": "✅ Тестовое имя установлено: {}"
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
                "UTC+6",
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
        self.running = False
        self.current_name = None

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
            # Для UTC+6 формата
            if timezone_str.upper().startswith("UTC"):
                # Преобразуем UTC+6 в Etc/GMT-6
                timezone_str = timezone_str.upper()
                offset = timezone_str[3:]  # Получаем "+6" или "-5"
                if offset.startswith("+"):
                    gmt_offset = f"Etc/GMT-{offset[1:]}"  # pytz использует обратную логику
                elif offset.startswith("-"):
                    gmt_offset = f"Etc/GMT{offset}"  # pytz использует обратную логику
                else:
                    # Если нет знака, предполагаем положительное смещение
                    gmt_offset = f"Etc/GMT-{offset}"
                
                # Проверяем что часовой пояс существует
                pytz.timezone(gmt_offset)
                return timezone_str  # Возвращаем оригинальный формат UTC+6
            else:
                # Для обычных имен часовых поясов
                pytz.timezone(timezone_str)
                return timezone_str
        except:
            return None

    def get_timezone_object(self):
        """Получаем объект часового пояса"""
        timezone_str = self.config["timezone"]
        
        # Обрабатываем формат UTC+6
        if timezone_str.upper().startswith("UTC"):
            timezone_str = timezone_str.upper()
            offset = timezone_str[3:]  # Получаем "+6" или "-5"
            if offset.startswith("+"):
                gmt_offset = f"Etc/GMT-{offset[1:]}"  # pytz использует обратную логику
            elif offset.startswith("-"):
                gmt_offset = f"Etc/GMT{offset}"  # pytz использует обратную логику
            else:
                # Если нет знака, предполагаем положительное смещение
                gmt_offset = f"Etc/GMT-{offset}"
            return pytz.timezone(gmt_offset)
        else:
            return pytz.timezone(timezone_str)

    def get_current_time(self):
        """Получаем текущее время в установленном часовом поясе"""
        try:
            tz = self.get_timezone_object()
            current_time = datetime.now(tz)
            return current_time.strftime("%H:%M"), current_time.strftime("%H:%M:%S")
        except Exception as e:
            # Если часовой пояс невалидный, используем UTC+6 по умолчанию
            try:
                tz = pytz.timezone("Etc/GMT-6")
                current_time = datetime.now(tz)
                return current_time.strftime("%H:%M"), current_time.strftime("%H:%M:%S")
            except:
                # В крайнем случае используем локальное время
                current_time = datetime.now()
                return current_time.strftime("%H:%M"), current_time.strftime("%H:%M:%S")

    async def update_name(self, force=False):
        """Обновляет имя пользователя"""
        try:
            current_time, full_time = self.get_current_time()
            new_name = self.strings("format").format(current_time)
            
            # Проверяем, изменилось ли имя
            if not force and self.current_name == new_name:
                return True, "no_change"
            
            # Получаем текущий профиль для проверки
            try:
                me = await self.client.get_me()
                current_first_name = me.first_name or ""
            except:
                current_first_name = ""
            
            # Пытаемся обновить имя
            try:
                await self.client(
                    self.client.functions.account.UpdateProfile(
                        first_name=new_name
                    )
                )
                self.current_name = new_name
                self.last_update = datetime.now()
                self.next_update = self.last_update + timedelta(seconds=self.config["update_interval"])
                return True, "updated"
            except Exception as e:
                # Если имя не изменилось (уже такое же)
                if "not modified" in str(e).lower():
                    self.current_name = new_name
                    return True, "no_change"
                else:
                    raise e
                    
        except Exception as e:
            # Логируем ошибку
            print(f"Ошибка при обновлении имени: {e}")
            return False, str(e)

    async def namechanger_task(self):
        """Задача для периодического обновления имени"""
        while self.running:
            try:
                success, status = await self.update_name()
                if not success:
                    print(f"Не удалось обновить имя: {status}")
                
                await asyncio.sleep(self.config["update_interval"])
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Ошибка в задаче обновления имени: {e}")
                await asyncio.sleep(self.config["update_interval"])

    async def start_namechanger(self):
        """Запускает автоматическую смену имени"""
        # Останавливаем существующую задачу если есть
        if self.running:
            await self.stop_namechanger()
        
        # Обновляем сразу при запуске
        success, status = await self.update_name(force=True)
        if not success and status != "no_change":
            return False
        
        # Запускаем периодическую задачу
        self.running = True
        self.db.set("NameChanger", "running", True)
        
        # Создаем асинхронную задачу
        self.task = asyncio.create_task(self.namechanger_task())
        return True

    async def stop_namechanger(self):
        """Останавливает автоматическую смену имени"""
        self.running = False
        self.db.set("NameChanger", "running", False)
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    @loader.command(
        ru_doc="Запустить автоматическую смену имени",
        alias="startname"
    )
    async def startnamecmd(self, message: Message):
        """Запустить автоматическую смену имени"""
        if self.running:
            await utils.answer(message, "⚠️ Автоматическая смена имени уже запущена!")
            return
        
        success = await self.start_namechanger()
        if success:
            timezone = self.config["timezone"]
            interval = self.config["update_interval"]
            await utils.answer(message, self.strings("started").format(timezone, interval))
        else:
            await utils.answer(message, "❌ Не удалось запустить смену имени!")

    @loader.command(
        ru_doc="Остановить автоматическую смену имени",
        alias="stopname"
    )
    async def stopnamecmd(self, message: Message):
        """Остановить автоматическую смену имени"""
        if not self.running:
            await utils.answer(message, "⚠️ Автоматическая смена имени уже остановлена!")
            return
        
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
        interval = self.config["update_interval"]
        
        # Получаем текущее время для отображения
        current_time, full_time = self.get_current_time()
        
        # Форматируем время последнего обновления
        last_update_str = "Никогда"
        if self.last_update:
            last_update_str = self.last_update.strftime("%H:%M:%S")
        
        # Форматируем время следующего обновления
        next_update_str = "Неизвестно"
        if self.running and self.next_update:
            now = datetime.now()
            if self.next_update > now:
                seconds_left = (self.next_update - now).seconds
                next_update_str = f"через {seconds_left} секунд"
            else:
                next_update_str = "Скоро"
        
        # Получаем текущее имя
        current_name = self.current_name or "Неизвестно"
        
        await utils.answer(
            message, 
            f"📊 <b>Статус смены имени</b>\n\n"
            f"• Статус: {status}\n"
            f"• Часовой пояс: {timezone}\n"
            f"• Интервал: {interval} секунд\n"
            f"• Текущее время: {full_time}\n"
            f"• Последнее обновление: {last_update_str}\n"
            f"• Следующее обновление: {next_update_str}\n"
            f"• Текущее имя: {current_name}"
        )

    @loader.command(
        ru_doc="Установить часовой пояс (пример: .settimezone UTC+6)",
        alias="settimezone"
    )
    async def settimezonecmd(self, message: Message):
        """Установить часовой пояс"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, "❌ Укажите часовой пояс!\nПример: <code>.settimezone UTC+6</code>")
            return
        
        validated_tz = self.validate_timezone(args)
        if validated_tz:
            old_timezone = self.config["timezone"]
            self.config["timezone"] = validated_tz
            
            current_time, full_time = self.get_current_time()
            await utils.answer(
                message, 
                f"✅ Часовой пояс изменен:\n"
                f"Старый: {old_timezone}\n"
                f"Новый: {validated_tz}\n"
                f"Текущее время: {full_time}"
            )
            
            # Если смена имени запущена, обновляем сразу
            if self.running:
                await self.update_name(force=True)
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
        ru_doc="Список популярных часовых поясов UTC+6",
        alias="timezones"
    )
    async def timezonescmd(self, message: Message):
        """Список популярных часовых поясов UTC+6"""
        current_timezone = self.config["timezone"]
        await utils.answer(
            message, 
            f"{self.strings('timezone_list')}\n\n"
            f"📍 Текущий часовой пояс: {current_timezone}"
        )

    @loader.command(
        ru_doc="Обновить имя вручную",
        alias="updatename"
    )
    async def updatenamecmd(self, message: Message):
        """Обновить имя вручную"""
        success, status = await self.update_name(force=True)
        if success:
            if status == "no_change":
                await utils.answer(message, self.strings("no_change"))
            else:
                current_time, full_time = self.get_current_time()
                await utils.answer(
                    message, 
                    f"✅ Имя обновлено вручную\n"
                    f"📍 Часовой пояс: {self.config['timezone']}\n"
                    f"🕐 Время: {full_time}"
                )
        else:
            await utils.answer(message, f"❌ Не удалось обновить имя!\nОшибка: {status}")

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
            f"📝 Имя будет: <code>{formatted_name}</code>"
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
            was_running = self.running
            if was_running:
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

    @loader.command(
        ru_doc="Установить тестовое имя для проверки",
        alias="testname"
    )
    async def testnamecmd(self, message: Message):
        """Установить тестовое имя для проверки"""
        try:
            test_name = "Lerman | TEST | #KERNEL"
            await self.client(
                self.client.functions.account.UpdateProfile(
                    first_name=test_name
                )
            )
            self.current_name = test_name
            await utils.answer(message, self.strings("test_name").format(test_name))
        except Exception as e:
            await utils.answer(message, f"❌ Не удалось установить тестовое имя: {e}")

    async def on_unload(self):
        """Вызывается при выгрузке модуля"""
        await self.stop_namechanger()
