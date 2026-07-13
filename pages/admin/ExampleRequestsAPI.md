---
title: "Примеры API запросов в HubEx для реализации интеграции"
url: "https://wiki.hubex.ru/docs/FAQ/RU/admin/ExampleRequestsAPI.html"
section: "admin"
content_hash: "ad3e2bf92fe6a736"
---

# Примеры API запросов в HubEx для реализации интеграции

## Содержание

* [Работа с заявками](https://wiki.hubex.ru/docs/FAQ/RU/admin/ExampleRequestsAPI.html#section1)
* [Работа с объектами](https://wiki.hubex.ru/docs/FAQ/RU/admin/ExampleRequestsAPI.html#section2)
* [Работа с компаниями](https://wiki.hubex.ru/docs/FAQ/RU/admin/ExampleRequestsAPI.html#section3)
* [Работа с пользователями](https://wiki.hubex.ru/docs/FAQ/RU/admin/ExampleRequestsAPI.html#section4)

---

## Работа с заявками

### Создание заявки

Создадим заявку, укажем "Компания-заказчик", выберем оборудование, вид работ, укажем адрес по заявке, тип заявки, откуда была подана заявка, укажем критичность заявки, крайний срок закрытия и заполним описание по заявке.

**Endpoint**: `POST /fsm/WORK/Tasks`

**Обязательные поля**:

* `TaskTypeID` - ID типа заявки
* `RequestMethodID` - Метод подачи заявки. Для интеграции рекомендуется использовать значение "4".

**Другие поля**:

* `CriticalityID` - ID критичности
* `deadline` - Крайний срок закрытия
* `companyID` - ID компании-заказчика
* `assetID` - ID объекта/оборудования
* `LocationID` - ID адреса/локации
* `WorkTypeID` - ID вида работ
* `Notes` - описание заявки - без html тегов (используется для отображения в списке заявок)
* `NotesHtml` - описание заявки - с html тегами (используется для отображения в заявке)

Полный перечень полей, а также их тип, можно посмотреть в SWAGGER. Список сервисов представлен в статье - [Начало работы с REST API HubEx](StartIntegrationAPI.md)

**Пример запроса**:

```
POST https://api.hubex.ru/fsm/WORK/Tasks
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
{
  "companyID": 123,
  "assetID": 456,
  "workTypeID": 7,
  "LocationID": 5946,
  "taskTypeID": 1,
  "criticalityID": 2,
  "RequestMethodID": 1,
  "deadline": "2025-07-08T15:00:00.000Z",
  "Notes": "Не работает принтер в кабинете 301",
  "NotesHtml": "<p>Не работает принтер в кабинете 301</p>\n"
}
```

**Пример успешного ответа**:

Status Code : **201 Created**

```
{
  "id": 5129,
  "number": "0207000000003"
}
```

**Как получить ID для полей**:

1. Компании: `GET /fsm/ES/Companies`
2. Оборудование: `GET /fsm/ES/Assets`
3. Виды работ: `GET /fsm/WORK/WorkTypes`
4. Типы заявок: `GET /fsm/WORK/TaskTypes`
5. Критичность: `GET /fsm/SLA/Criticalities`
6. Адрес: `POST fsm/ES/locations`, или использовать адрес из Объекта
7. И так далее, endpoint представлены в SWAGGER. Список сервисов представлен в статье - [Начало работы с REST API HubEx](StartIntegrationAPI.md)

---

### Изменение заявки

Поменяем значение "Компания-заказчик" и "Крайний срок закрытия"

**Endpoint**: `PATCH /fsm/WORK/Tasks/{taskID}`

**Пример запроса**:

```
PATCH https://api.hubex.ru/fsm/WORK/Tasks/789
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
{
  "companyID": 17,
  "deadline": "2025-07-10T14:08:00.000Z"
}
```

**Пример успешного ответа**:

Status Code : **202 Accepted**

---

### Изменение дополнительных полей заявки

**Endpoint**: `POST fsm/WORK/taskAttributes`

**Пример запроса**:

```
POST https://api.hubex.ru/fsm/WORK/taskAttributes
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
[{
  "taskID":5130,
  "data":[
  {
    "attributeID":7,
    "value":true
  },
  {
    "attributeID":13,
    "value":"NFC отсканирован"
  },
  {
    "attributeID":68,
    "value":""
  }]
}]
```

**Пример успешного ответа**:

Status Code : **202 Accepted**

Для получаения списка ID дополнительных полей требуется использовать **Endpoint**: `GET fsm/COMMON/Attributes/?isRelevantForTask=true&isDeleted=false`

---

### Работа со стадиями

**Получение списка доступных стадий для заявки**:

```
GET https://api.hubex.ru/fsm/Tasks/{taskID}/stages/next
```

Где taskID - это id заявки

**Изменение стадии**:

**Endpoint**: `POST fsm/WORK/taskstagingHistory`

```
POST https://api.hubex.ru/fsm/WORK/taskstagingHistory
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
{
  "taskID": 789,
  "taskStageID": 5  // ID стадии "Отказ заказчика"
}
```

**Пример успешного ответа**:

Status Code : **201 Created**

```
{
  "stageId":5,
  "isFinalStage":false,
  "errors":[]
  }
```

---

### Сообщения

**Отправка сообщения в чат с командой**:

**Endpoint**: `POST fsm/WORK/Tasks/{taskID}/conversation/`

```
POST https://api.hubex.ru/fsm/WORK/Tasks/5131/conversation/
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
{
  "isExternal":false,
  "attachments":[],
  "message":"Принял в работу"
  }
```

Где, "isExternal" - это выбор чата, если false - чат с командой, если tue - чат с заказчиком. Для отправки сообщения одновременно и в чат с заказчиком и в чат с командой, требуется дважды отправить запрос POST https://api.hubex.ru/fsm/WORK/Tasks/{taskID}/conversation/, со значением параметра "isExternal" = true и false.

**Получение сообщений**:

**Endpoint**: `GET fsm/WORK/Tasks/{taskID}/conversation/`

```
GET https://api.hubex.ru/fsm/WORK/Tasks/5131/conversations/?thumbnailSize=128
```

**Пример ответа**:

```
[
    {
        "id": 1,
        "created": "2025-07-02T15:15:04",
        "message": "Приехал на объект",
        "isExternal": false,
        "author": {
            "tenantMemberID": 0,
            "isTechnician": false,
            "isCustomer": false,
            "id": 1,
            "firstName": "Скобеев",
            "lastName": "Павел",
            "middleName": ""
        },
        "delivery": {
            "toAnyone": true,
            "toAll": true,
            "toCurrentUser": "2025-07-02T15:15:04"
        },
        "read": {
            "byAnyone": false,
            "byAll": false,
            "byCurrentUser": "2025-07-02T15:15:04",
            "isReadExpected": false
        }
    },
    {
        "id": 2,
        "created": "2025-07-02T15:15:23",
        "message": "Работы выполнены. Просьба принять.",
        "isExternal": true,
        "author": {
            "tenantMemberID": 0,
            "isTechnician": false,
            "isCustomer": false,
            "id": 1,
            "firstName": "Скобеев",
            "lastName": "Павел",
            "middleName": ""
        },
        "delivery": {
            "toAnyone": true,
            "toAll": true,
            "toCurrentUser": "2025-07-02T15:15:23"
        },
        "read": {
            "byAnyone": false,
            "byAll": false,
            "byCurrentUser": "2025-07-02T15:15:23",
            "isReadExpected": false
        }
    }
]
```

---

### Файлы

**Добавление файла** (используйте FormData):

**Endpoint**: `POST fsm/WORK/taskAttachments/upload/fromForm`

```
POST https://api.hubex.ru/fsm/WORK/taskAttachments/upload/fromForm
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: multipart/form-data
Body:
  taskID: 5131
  file: [ваш файл] //в бинарном формате
  isPublic: false
  isIgnorePossibleDuplication: true
```

**Пример ответа**:

```
{
    "taskID": 5131,
    "attachmentID": 279,
    "md5Hash": "8257360CCAAD8A3F49AB4E43283DCDF2",
    "fileName": "Web1.jpg",
    "isProtected": false
}
```

**Получение списка файлов**:

**Endpoint**: `GET fsm/WORK/tasks/{taskID}/attachments`

```
GET https://api.hubex.ru/fsm/WORK/tasks/5131/attachments?thumbnailSize=128
```

**Пример ответа**:

```
{
    "279": {
        "fileName": "Web1.jpg",
        "isUploaded": true,
        "thumbnailUrl": "https://239911.selcdn.ru/DEVTenant000041/_thumbnails/D395771085AAB05244A4FB8FD91BF4EE_128x128?temp_url_sig=ad34207918611c2bca7264c4a114c1c17de8d08a&temp_url_expires=1751470458",
        "isProtected": false,
        "size": 86674,
        "created": "2025-07-02T15:33:57"
    }
}
```

Для получения миниатюры изображения используйте **"thumbnailUrl"**

Для получения исходного файла используйте **Endpoint**: `GET fsm/COMMON/attachments/279?noRedirect=true`, где 279 - это id вложения.

---

## Работа с объектами

### Создание объекта

Созданим объект с именем "Кондиционер", с указанной "Компания-владелец", "Тип оборудования", "Класс оборудования", укажем, что оборудование не мобильное, без родительского объекта и сразу опубликуем его.

**Endpoint**: `POST /fsm/ES/Assets`

**Обязательные поля**:

* `Name` - Имя объекта/оборудования
* `AssetTypeID` - ID типа оборудования
* `AssetClassID` - ID класса оборудования
* `CompanyID` - ID компании

**Пример необязательных полей**:

* `IsAutoPublish` - Признак публикации объекта
* `IsMobileAsset` - Признак "Мобильное оборудование"

Полный перечень полей, а также их тип, можно посмотреть в SWAGGER. Список сервисов представлен в статье - [Начало работы с REST API HubEx](StartIntegrationAPI.md)

**Пример запроса**:

```
POST https://api.hubex.ru/fsm/ES/Assets
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
{
"Name":"Кондиционер",
"CompanyID":19,
"AssetTypeID":1,
"AssetClassID":1,
"IsMobileAsset":false,
"IsInheritParentDistricts":false,
"IsAutoPublish":true
}
```

**Пример успешного ответа**:

Status Code : **201 Created**

```
{
  "name":"Кондиционер",
  "id":1017
  }
```

Где id - это id созданного объекта/оборудования в системе

**Как получить ID для полей**:

1. Компании: `GET /fsm/ES/Companies`
2. Тип оборудования: `GET /fsm/ES/assetTypes`
3. Класс оборудования: `GET /fsm/ES/assetClasses`
4. И так далее, endpoint представлены в SWAGGER. Список сервисов представлен в статье - [Начало работы с REST API HubEx](StartIntegrationAPI.md)

### Изменение объекта

Поменям для нашего объекта признак мобильности оборудования и укажем "Описание".

**Endpoint**: `PUT /fsm/ES/Assets/{assetID}`

**Пример запроса**:

```
PATCH https://api.hubex.ru/fsm/ES/Assets/1017
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
{
"Name":"Кондиционер",
"CompanyID":19,
"AssetTypeID":1,
"AssetClassID":1,
"IsMobileAsset":true,
"IsInheritParentDistricts":false,
"IsAutoPublish":true,
"Notes":"Объект установлен в правом углу помещения!"
}
```

Обратите внимание, что для изменения объекта используется метод **PUT**, который обновляет **все поля** по объекту, в связи с этим для изменения объекта **требуется передавать все поля** с текущим значением + поле, которое планируется поменять, уже с новым значением.

---

### Публикация объекта

**Endpoint**: `PUT /fsm/ES/Assets/{assetID}/publish`

**Пример запроса**:

```
PUT https://api.hubex.ru/fsm/ES/Assets/456/publish
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
```

**Пример успешного ответа**:

Status Code : **202 Accepted**

---

## Работа с компаниями

### Создание компании

Создадим компанию с типом "Заказчик" и именем "ПАО Ретроспектива".

**Endpoint**: `POST /fsm/ES/Companies`

**Пример запроса**:

```
POST https://api.hubex.ru/fsm/ES/Companies
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
[
  {
  "isEmployer":true,
  "registrationTypeID":"3",
  "name":"ПАО Ретроспектива"
  }
]
```

**Пример успешного ответа**:

Status Code : **201 Created**

```
[
  21
]
```

Где 21 - id созданной компании

**Как получить ID для полей**:

1. Тип компании: `GET fsm/ES/CompanyRegistrationTypes/`
2. Список банков: `GET /fsm/COMMON/banks/`
3. Список контактов тенанта: `GET /fsm/COMMON/Contacts/?isDeleted=false`
4. И так далее, endpoint представлены в SWAGGER. Список сервисов представлен в статье - [Начало работы с REST API HubEx](StartIntegrationAPI.md)

### Изменение компании

**Endpoint**: `PUT /fsm/ES/Companies/`

**Пример запроса**:

```
PUT https://api.hubex.ru/fsm/ES/Companies/
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
[
  {
  "id":19,
  "name":"ОАО \"Информ-бюро\"",
  "customerOrgUnit":{
    "name":"Клиенты",
    "id":56},
  "staffOrgUnit":{
    "name":"Сотрудники",
    "id":57
    },
  "fullName":"ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ \"ВИЛМИ\"",
  "iec":"7896788",
  "isContractorHolder":false,
  "isEmployer":true,
  "isOurCompany":false,
  "psrn":"2131232131231",
  "okpo":"3214234231423234",
  "registeredOffice":"109428, г Москва, Рязанский р-н, ул 2-я Институтская, д 2/10, кв 19",
  "registeredOfficeNote":"Офисное здание",
  "tin":"543643566",
  "location":{
    "dateFrom":"2025-06-03T12:43:20",
    "dateTill":"9999-12-31T23:59:59",
    "timezoneUtcOffsetMinutes":180,
    "timezoneID":2,
    "countryID":182,
    "countryTwoSymbolCode":"RU",
    "address":"5-я линия Васильевского острова, 20, Санкт-Петербург, Россия",
    "coordinate":"59.940833:30.283763",
    "id":3434
    },
  "fileList":[],
  "files":[],
  "contacts":[],
  "registrationTypeID":3,
  "bankAccounts":[{
    "companyID":19,
    "bank":{
      "id":3,
      "name":"ПАО Банк \"ФК Открытие\"",
      "bic":"555433434",
      "correspondingAccount":"423563400450344"
      },
    "companyBankAccountID":1,
    "checkingAccount":"25436645344545",
    "companyName":"ОАО \"Информ-бюро\"",
    "currency":{
      "id":1,
      "shortName":"Рубль",
      "asciiCode":"%E2%82%BD"
      },
    "isDefault":true,
    "id":3,
    "name":"ПАО Банк \"ФК Открытие\"",
    "bic":"43545555",
    "correspondingAccount":"547721346743567"
    }],
  "checkingAccount":"437775676565455"
]
```

**Пример успешного ответа**:

Status Code : **202 Accepted**

Обратите внимание, что для изменения компании используется метод **PUT**, который обновляет **все поля** по компании, в связи с этим для изменение компании **требуется передавать все поля** с текущим значением + поле, которое планируется поменять, уже с новым значением.

---

## Работа с пользователями

### Создание пользователя

Создадим мобильного сотрудника "Кулибин Павел", мужчина, с email - kulibin@mail.ru, с отслеживанием месторасположения, добавим ему роль и назначим необходимые участки.

**Endpoint**: `POST /fsm/ADM/Users`

**Пример запроса**:

```
POST https://api.hubex.ru/fsm/ADM/Users
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
{
  "firstName":"Павел",
  "lastName":"Кулибин",
  "sexID":"1",
  "email":"kulibin@mail.ru",
  "geotrackingModeID":"1",
  "isTechnician":true,
  "mobilityID":1,
  "rate":null,
  "rateCurrencyID":1
}
```

**Пример успешного ответа**:

Status Code : **201 Created**

**Дополнительно, требуется еще сделать запросы:**:

1. Назначение роли пользователю: `POST fsm/ADM/UserRoles/`
2. Назначение участков пользователю: `POST /fsm/ADM/UserDistricts/`

---

### Изменение пользователя

**Endpoint**: `PUT /fsm/ADM/Users/{userID}`

**Пример запроса**:

```
PUT https://api.hubex.ru/fsm/ADM/Users/171/
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
{
  "firstName":"Павел",
  "lastName":"Кулибин",
  "middleName":"Сергеевич",
  "sexID":1,
  "oldEmail":"kulibin@mail.ru",
  "email":"kulibin@mail.ru",
  "geotrackingModeID":"1",
  "isTechnician":true,
  "mobilityID":1,
  "rate":null,
  "rateCurrencyID":1
}
```

**Пример успешного ответа**:

Status Code : **202 Accepted**

Обратите внимание, что для изменения сотрудника используется метод **PUT**, который обновляет **все поля** по сотруднику, в связи с этим для изменение сотрудника **требуется передавать все поля** с текущим значением + поле, которое планируется поменять, уже с новым значением.

---

### Блокировка пользователя

**Endpoint**: `POST /fsm/ADM/Users/{userID}/`

**Пример запроса**:

```
PUT https://api.hubex.ru/fsm/ADM/Users/171/
Headers:
  Authorization: Bearer YOUR_ACCESS_TOKEN
  Content-Type: application/json
Body:
{
  "firstName":"Павел",
  "lastName":"Кулибин",
  "middleName":"Сергеевич",
  "sexID":1,
  "oldEmail":"kulibin@mail.ru",
  "email":"kulibin@mail.ru",
  "geotrackingModeID":"1",
  "isTechnician":true,
  "mobilityID":1,
  "banReasonID":"1",
  "banTill":"9999-12-30T20:59:00",
  "rate":null,
  "rateCurrencyID":1
}
```

**Пример успешного ответа**:

Status Code : **202 Accepted**

Обратите внимание, что для изменения сотрудника используется метод **PUT**, который обновляет **все поля** по сотруднику, в связи с этим для изменение сотрудника **требуется передавать все поля** с текущим значением + поле, которое планируется поменять, уже с новым значением.

Где, **"banReasonID"** - это признак блокировки пользователя, а **"banTill"** - дата, до которой пользователь будет заблокирован (в примере - навсегда).

---

* [Перейти в меню](http://wiki.hubex.ru)
