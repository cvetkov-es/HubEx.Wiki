# Индекс вики HubEx

> **Что здесь:** аннотированный каталог страниц вики HubEx (секции admin и user), по темам.
> **Когда сюда идти:** любой вопрос про поведение/настройку продукта HubEx.
> **Источник:** wiki.hubex.ru · Обновляется: `python3 tools/wiki_cli.py update --recompress`

Копии страниц — в [pages/](pages/). Страницы-«грабли» помечены ⚠.
Релиз-ноуты — в отдельном [releasenotes-index.md](releasenotes-index.md).

## Заявки и ЖЦ

- [BusinessProcess](pages/admin/BusinessProcess.md) — типовой бизнес-процесс (ЖЦ) заявки на ремонт: таблица стадий и допустимых переходов.
- [TicketLifeCycle](pages/admin/TicketLifeCycle.md) — настройка жизненного цикла заявки: маршрут, переходы между стадиями, ветки ЖЦ.
- [StageType](pages/admin/StageType.md) — настройка стадий заявки: действия и требования при переходе (QR-код, чек-лист, подписанный акт).
- [StatusType](pages/admin/StatusType.md) — создание статуса заявки (название, цвет) для отображения заказчику.
- [StageVSStatus](pages/admin/StageVSStatus.md) — ⚠ разница между Стадией (для сотрудников) и Статусом (для заказчика).
- [TicketType](pages/admin/TicketType.md) — сущность «Тип заявки»: ЖЦ, маска номера, срок закрытия, доступные виды работ и участки.
- [TicketAttribute](pages/admin/TicketAttribute.md) — создание атрибутов (доп.полей) для пунктов чек-листа.
- [TicketsAgreement](pages/admin/TicketsAgreement.md) — настройка линейного и параллельного согласования заявок на примере закупки ТМЦ.
- [Actuality](pages/admin/Actuality.md) — справочник «Актуальность заявки» для оптимизации очередности выполнения.
- [Criticality](pages/admin/Criticality.md) — справочник критичности заявки и её роль в расчёте SLA.
- [CreatingTicket](pages/user/CreatingTicket.md) — создание заявки: поля формы, список заявок, назначение исполнителей, срок закрытия.
- [ChangingStatus](pages/user/ChangingStatus.md) — переход заявки по стадиям и её мягкое удаление.
- [ChildTicket](pages/user/ChildTicket.md) — создание, отслеживание и отображение дочерних заявок.
- [ElectedTicket](pages/user/ElectedTicket.md) — копирование и удаление заявок, поиск удалённых, избранное.
- [AcceptanceTicket](pages/user/AcceptanceTicket.md) — самостоятельное назначение заявки исполнителем из общего списка.
- [SeveralEngineers](pages/user/SeveralEngineers.md) — три способа назначить нескольких исполнителей на заявку.
- [PlannedTickets](pages/user/PlannedTickets.md) — создание и периодичность плановых заявок для регулярного обслуживания.
- [PlannedTicketsSchedule](pages/user/PlannedTicketsSchedule.md) — график обслуживания объектов как табличное представление плановых заявок.
- [CustomerAgreement](pages/admin/CustomerAgreement.md) — настройка согласования заявки с заказчиком: стадии, статусы, оповещения.
- [ChoiceWorkType](pages/user/ChoiceWorkType.md) — от чего зависит выбор вида работ в заявке.
- [Filters](pages/user/Filters.md) — режимы списка заявок, фильтры, быстрые фильтры, поиск.
- [GroupActionsForTickets](pages/user/GroupActionsForTickets.md) — массовое назначение исполнителей и массовое удаление заявок.
- [HistoryOfChanges](pages/user/HistoryOfChanges.md) — вкладка «История изменений» заявки: фиксация событий по полям и стадиям.
- [ElementsOfInterface](pages/admin/ElementsOfInterface.md) — настройка доступа к полям формы заявки (RO/RW/RWM) по ролям и стадиям.
- [HowToDealWithWhiteScreen](pages/user/HowToDealWithWhiteScreen.md) — причина пустой формы заявки: не настроен доступ к полям для новой стадии.
- [UsersRequests](pages/user/UsersRequests.md) — поле «Инициатор заявки», создание/выбор инициатора, история обращений.
- [AlternativeWays](pages/user/AlternativeWays.md) — альтернативные способы подачи заявки: паспорт объекта (QR), email, форма на сайте.
- [TicketMail](pages/admin/TicketMail.md) — интеграция по email (пересылка, IMAP) для автосоздания заявок из писем.
- [HiddenObjectsTicketsUsers](pages/user/HiddenObjectsTicketsUsers.md) — ⚠ причины, почему пользователь не видит заявки/объекты/исполнителей: фильтры vs права доступа.

## Объекты

- [ObjectsType](pages/admin/ObjectsType.md) — типы оборудования: настройки (обязательный адрес, привязка видов работ), иерархия объект/оборудование.
- [ObjectClass](pages/admin/ObjectClass.md) — классы оборудования: группировка объектов и заявок по характеристикам (цена, производитель).
- [PlacesVSObjectsClass](pages/admin/PlacesVSObjectsClass.md) — ⚠ разница между Классом оборудования и Участком.
- [CreatingObjects](pages/user/CreatingObjects.md) — создание карточки объекта/оборудования: поля, дочерние объекты, QR-коды, история обслуживания.
- [CreatingObjTemplates](pages/user/CreatingObjTemplates.md) — создание шаблона объекта/оборудования, приёмка и маркировка через мобильное приложение по QR.
- [ObjectEditing](pages/user/ObjectEditing.md) — три способа редактирования данных объекта в мобильном приложении.
- [ChangeOfObjectType](pages/user/ChangeOfObjectType.md) — изменение типа оборудования в карточке объекта.
- [TheDifferenceBetweenObjectTypes](pages/user/TheDifferenceBetweenObjectTypes.md) — ⚠ иерархия объектов: родительский объект с адресом vs дочерний без адреса.
- [MobileObjects](pages/user/MobileObjects.md) — мобильное оборудование (изменяемый адрес) и обновление адреса через заявку.
- [ObjectListInMob](pages/user/ObjectListInMob.md) — список объектов в мобильном приложении, паспорт объекта, создание заявки из паспорта.
- [DeletedObjects](pages/user/DeletedObjects.md) — способы удаления/блокировки компаний, объектов, заявок и почему удаление всегда «мягкое».
- [FloorPlan](pages/user/FloorPlan.md) — план помещения объекта и указание расположения объекта на плане при подаче заявки.
- [HowToMakePassport](pages/user/HowToMakePassport.md) — создание паспорта объекта через привязку QR-кода к объекту и шаблону заявки.
- [CreatingTaskTemplates](pages/user/CreatingTaskTemplates.md) — создание шаблона заявки и QR-кода, паспорт объекта, подача заявки по QR-коду, подтверждение пребывания на объекте.
- [QRcodeMain](pages/user/QRcodeMain.md) — три сценария использования QR-кода: создание объектов, подача заявок, незарегистрированные пользователи.
- [GroupActions](pages/user/GroupActions.md) — быстрые фильтры и массовое изменение параметров списка объектов.

## Компании и договоры

- [CreatingCompany](pages/user/CreatingCompany.md) — создание карточки компании: виды, реквизиты, контакты, договоры, импорт/экспорт.
- [CreatingCustomer](pages/user/CreatingCustomer.md) — создание карточки заказчика и перевод заказчика в сотрудники.
- [CreatingUser](pages/user/CreatingUser.md) — создание карточки сотрудника (Общее/Квалификация/Трудоустройство), перевод сотрудника в заказчики.
- [Contacts](pages/user/Contacts.md) — контактные лица в карточках компании и объекта, доступ к ним в заявке.
- [ContractSchedule](pages/user/ContractSchedule.md) — отчёт «График действия договоров»: сроки договоров и заявки вне периода действия.

## Пользователи, роли, участки, навыки

- [Roles](pages/admin/Roles.md) — сущность «Роль», базовые роли (Заказчик, Сервисный специалист, Диспетчер), доступ по участкам и полномочиям.
- [Powers](pages/admin/Powers.md) — тематические блоки полномочий ролей в консоли администратора.
- [UI_Permissions](pages/admin/UI_Permissions.md) — раздел UI-полномочий для элементов интерфейса.
- [Places](pages/admin/Places.md) — сущность «Участок»: классификация объектов, сотрудников, заказчиков и типов заявок.
- [Skills](pages/admin/Skills.md) — сущность «Навык»: классификация объектов и сотрудников для автоназначения.
- [ServiceUsers](pages/admin/ServiceUsers.md) — служебные учётные записи: Пользователь API и Анонимный пользователь.
- [RoleVSPosition](pages/user/RoleVSPosition.md) — ⚠ разница между Ролью (права доступа) и Должностью (справочное поле).
- [SuperAndUsualUser](pages/user/SuperAndUsualUser.md) — ⚠ разница между «Системным администратором» без ограничений и обычной учётной записью владельца тенанта.
- [EngineerVSCustomer](pages/user/EngineerVSCustomer.md) — ⚠ разница прав и возможностей ролей Сотрудник и Заказчик.
- [EnterToMob](pages/user/EnterToMob.md) — регистрация и вход сотрудника/заказчика в мобильные приложения.
- [SelfRegister](pages/user/SelfRegister.md) — подача заявки по QR без приложения и самостоятельная регистрация заказчика.
- [HowToSendInvitation](pages/user/HowToSendInvitation.md) — автоотправка приглашения (email/sms) новому сотруднику или заказчику.
- [ViewRestriction](pages/user/ViewRestriction.md) — настройка доступа по ролям к файлам, прикреплённым к заявке или объекту.
- [WorkSchedule](pages/admin/WorkSchedule.md) — графики работы сотрудников (недельный, сменный) для автоназначения.
- [Schedule](pages/user/Schedule.md) — графики работы: типовые графики, недельные/сменные, привязка к сотрудникам и объектам, «Я на смене».
- [OnDuty](pages/user/OnDuty.md) — индивидуальный график и функционал «На смене» (начало/завершение смены).

## SLA и критичности

- [SLA](pages/admin/SLA.md) — правила расчёта крайнего срока закрытия заявки в разрезе типа заявки, критичности, вида работ, заказчика, объекта.
- [RulesOfChoice](pages/admin/RulesOfChoice.md) — правила автоназначения исполнителя (навыки, вид работ, график, участок).
- [RulesOfChoiceGEO](pages/user/RulesOfChoiceGEO.md) — автоназначение ближайшего по геопозиции исполнителя.
- [WorkType](pages/admin/WorkType.md) — сущность «Вид работ»: классификация услуг, чек-лист, стоимость, срок закрытия.

## Чек-листы

- [Checklists](pages/user/Checklists.md) — создание чек-листов и атрибутов, привязка к объектам/видам работ, заполнение в мобильном приложении.

## Работы и акты

- [ActOFAcceptance](pages/user/ActOFAcceptance.md) — формирование Акта выполненных работ, расчёт стоимости, подпись заказчика.
- [AttachingFiles](pages/user/AttachingFiles.md) — прикрепление выполненных работ к заявке в web и мобильном приложении, офлайн-режим.
- [PrintedFormAct](pages/user/PrintedFormAct.md) — печатная форма «Сервисный акт»: фильтры, варианты НДС, экспорт.
- [PrintedFormActOfAccounting](pages/user/PrintedFormActOfAccounting.md) — «Бухгалтерский акт» с обязательными по 402-ФЗ реквизитами.
- [PrintingFormDesigner](pages/user/PrintingFormDesigner.md) — конструктор печатных форм: шаблоны с переменными и таблицами, ограничения.
- [PaymentInvoice](pages/user/PaymentInvoice.md) — печатная форма «Счёт на оплату» по выполненным работам, фильтры, НДС.
- [Prices](pages/user/Prices.md) — стоимости в HubEx: ставка сотрудников, стоимость видов работ и материалов, стоимость заявки, расчёт зарплаты.
- [Rating](pages/user/Rating.md) — система оценки заявок и рейтинга сотрудников, видимость по ролям и стадиям.
- [OfflineMode](pages/user/OfflineMode.md) — офлайн-режим мобильного приложения исполнителя: заявки, работы, чек-листы, одна стадия перехода.
- [TicketWithMaterials](pages/user/TicketWithMaterials.md) — вкладка «Необходимые материалы» в заявке (рекомендация без списания).

## Склад

- [Materials](pages/user/Materials.md) — загрузка материалов и создание складов через Excel-импорт, изменение остатков.
- [MaterialsNew](pages/user/MaterialsNew.md) — расширенная версия статьи про склады и материалы, идея «рюкзака» сотрудника.
- [InventoryAccounting](pages/user/InventoryAccounting.md) — ⚠ два сценария складского учёта: с внешней системой (1С) и без неё.
- [SettingsWithMaterials](pages/user/SettingsWithMaterials.md) — доступ к меню «Склады» и право на добавление материалов в выполненную работу по ролям.
- [Withdrawals](pages/user/Withdrawals.md) — расход материалов по заявке и отчёт по израсходованным материалам.
- [WarehouseOperations](pages/user/WarehouseOperations.md) — страница-заглушка (реального содержания нет).
- [Warehouses](pages/user/Warehouses.md) — страница-заглушка (реального содержания нет).
- [WarehousesGoodsReceipt](pages/user/WarehousesGoodsReceipt.md) — страница-заглушка (реального содержания нет).

## Уведомления и каналы

- [Notifications](pages/admin/Notifications.md) — настройка оповещений: правила выбора получателя и триггеры (push/email).
- [NotificationInMob](pages/user/NotificationInMob.md) — лента уведомлений в мобильном приложении исполнителя.
- [NotificationInWeb](pages/user/NotificationInWeb.md) — лента уведомлений в web-приложении для руководителей и диспетчеров.
- [HowToManageNotifications](pages/user/HowToManageNotifications.md) — настройка email-уведомления о выполнении заявки через копирование триггера.
- [HowNotificationsToMobile](pages/user/HowNotificationsToMobile.md) — проверка настроек уведомлений на мобильном устройстве.
- [HowToNotificationsToMobile](pages/user/HowToNotificationsToMobile.md) — включение уведомлений от мобильных приложений на устройстве (близко по содержанию к HowNotificationsToMobile).
- [Messages](pages/user/Messages.md) — сообщения по заявке в web и мобильном приложениях, участники чата, разделение чатов с командой и заказчиком.
- [AnswerTemplate](pages/user/AnswerTemplate.md) — шаблоны ответов для чатов с заказчиками и исполнителями.
- [TelegramIntegration](pages/admin/TelegramIntegration.md) — интеграция с Telegram-ботом для приёма и обработки заявок от заказчиков.
- [HowToContactSupport](pages/user/HowToContactSupport.md) — обращение в техподдержку HubEx через чат в web и кнопку в мобильном приложении.

## Доп.поля

- [AdditionalFields](pages/user/AdditionalFields.md) — создание и использование дополнительных полей для компаний, объектов, заявок, работ, чек-листов, договоров.

## Аналитика

- [GeneralAnalytics](pages/user/GeneralAnalytics.md) — панель Power BI «Общая аналитика»: KPI, динамика поступивших заявок, разрезы.
- [EngineersAnalytics](pages/user/EngineersAnalytics.md) — отчёт Power BI по сотрудникам: заявки и SLA, отработанное время, KPI, рейтинг.
- [ObjectsAnalytics](pages/user/ObjectsAnalytics.md) — отчёт по объектам обслуживания: KPI (MTBF, MTTR), динамика, география.
- [ClientsAnalytics](pages/user/ClientsAnalytics.md) — отчёт «Отчёт для клиента» на Power BI.
- [ProcessEfficiency](pages/user/ProcessEfficiency.md) — отчёт «Анализ эффективности процессов»: проблемы в бизнес-процессах, сравнение эффективности, время прохождения стадий.
- [TicketsReport](pages/user/TicketsReport.md) — раздел «Срез по заявкам»: диаграммы по стадиям, просрочкам, компаниям, загруженности.
- [Export](pages/user/Export.md) — экспорт заявок, медиафайлов, объектов, пользователей, компаний в Excel.
- [Import](pages/user/Import.md) — импорт объектов, пользователей, компаний, заявок через Excel-шаблоны, лимиты и обязательные поля.
- [GeoPosition](pages/user/GeoPosition.md) — просмотр текущей геопозиции сотрудников и заявок на карте.
- [Geotracking](pages/user/Geotracking.md) — «История перемещений»: маршруты, остановки, пробег сотрудников на карте.
- [TicketsOnMap](pages/user/TicketsOnMap.md) — заявки и сотрудники на карте, календарь загруженности, назначение через карту/календарь.
- [UserOnMap](pages/user/UserOnMap.md) — способы посмотреть геопозицию сотрудника и условие включения геотрекинга.
- [Calendar](pages/user/Calendar.md) — календарь заявок (день/неделя/месяц) в web и мобильном приложении, назначение и уведомления.

## Администрирование и деплой

- [AboutHubEx](pages/admin/AboutHubEx.md) — общее описание платформы HubEx: сравнение с Help Desk/ITSM/CRM/ТОиР/SCADA, компоненты, способы доработки, стек.
- [HowToEnterTheAdmin](pages/admin/HowToEnterTheAdmin.md) — вход в консоль администратора и что делать при нехватке прав.
- [Deployment](pages/admin/Deployment.md) — сравнение вариантов развёртывания: публичное облако, облако на выделенных серверах, on-premise.
- [OnPremise](pages/admin/OnPremise.md) — страница-заглушка про On-Premise (реального содержания нет).
- [Branding](pages/user/Branding.md) — требования к логотипу компании и брендирование web/мобильного приложения (подписка «Корпорация»).
- [MobileDevice](pages/user/MobileDevice.md) — технические требования к Android/iOS-устройствам для мобильных приложений HubEx.
- [GeoSettings](pages/user/GeoSettings.md) — включение геолокации и настроек энергосбережения на iPhone/Samsung/Xiaomi/Huawei.
- [GEOinMob](pages/user/GEOinMob.md) — зачем нужна геолокация мобильному приложению исполнителя и какие настройки телефона мешают GPS.
- [KnowledgeBase](pages/user/KnowledgeBase.md) — база знаний HubEx как виджет партнёра HiHub: рабочие пространства, разделы, статьи, роли доступа.
- [HubExAI](pages/user/HubExAI.md) — встроенный AI-чат-бот HubEx AI: назначение, вызов, вопросы прямо в интерфейсе.
- [HubExStepByStep](pages/user/HubExStepByStep.md) — первые шаги в HubEx: заполнение справочников и способы создания заявок.
- [Glossary](pages/user/Glossary.md) — глоссарий основных терминов HubEx.

## Интеграции и API

- [RESTAPI](pages/admin/RESTAPI.md) — обзор REST API: HTTP-методы, примеры интеграций с CRM, 1С, мессенджерами, системами мониторинга.
- [StartIntegrationAPI](pages/admin/StartIntegrationAPI.md) — начало работы с REST API: сервисный пользователь, access token, примеры запросов (Postman, cURL, Python).
- [ExampleRequestsAPI](pages/admin/ExampleRequestsAPI.md) — примеры REST API-запросов: заявки, объекты, компании, пользователи, стадии, сообщения, файлы.
- [Integration](pages/admin/Integration.md) — интеграция с Битрикс24 через сервис Albato (связки, токены, триггеры).
- [IntegrationBitrix24](pages/admin/IntegrationBitrix24.md) — альтернативная интеграция с Битрикс24 через приложение из Маркетплейса Битрикс24.
- [SSOintegration](pages/admin/SSOintegration.md) — единый вход SSO: протоколы (SAML, OAuth2/OIDC, LDAP), настройка через Keycloak.
- [HowToManageGmailIntegration](pages/user/HowToManageGmailIntegration.md) — настройка доступа «ненадёжных приложений» в Google для интеграции HubEx с Gmail.
- [Integration](pages/user/Integration.md) — страница-заглушка раздела «Руководство пользователя» (реального содержания нет).

## Моб.приложения

- [CustomerApp](pages/user/CustomerApp.md) — мобильное приложение HubEx Заказчик: вход, создание заявки, чат, отмена, приёмка работ, оценка исполнителя.
- [CustomerWeb](pages/user/CustomerWeb.md) — клиентский веб-портал заказчика: вход, создание заявки, чат, печать акта, аналитика.
- [RouteToObject](pages/user/RouteToObject.md) — построение маршрута до объекта через внешние карты (Яндекс, 2ГИС, Google).

