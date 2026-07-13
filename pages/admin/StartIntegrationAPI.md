---
title: "Начало работы с REST API HubEx"
url: "https://wiki.hubex.ru/docs/FAQ/RU/admin/StartIntegrationAPI.html"
section: "admin"
content_hash: "696caf08f152c57a"
---

# **Начало работы с REST API HubEx**

Этот раздел поможет вам быстро подключиться к API HubEx, настроить авторизацию и выполнить первые запросы. Мы рассмотрим пошаговый процесс от получения токена до тестирования API.

---

## **1. Подготовка к работе с API**

Перед началом интеграции убедитесь, что у вас есть:

* Доступ к **административной панели HubEx** (роль с правами на управление API)
* Возможность отправлять **HTTP-запросы** (через Postman, cURL, Python, PHP и т. д.)
* Базовое понимание **REST API** и **формата JSON**

---

## **2. Настройка API-пользователя и получение токена**

### **Шаг 1. Создание служебного пользователя**

1. Войдите в **административную панель HubEx**.
2. Перейдите в раздел:
   **`Интеграция → Служебные пользователи`**.
3. Нажмите **"Пользователь API"**.
4. Выберите:

   * **Роли**
   * **Участки**

### **Шаг 2. Генерация сервисного токена**

1. В разделе "Токен доступа" нажмите **"Сгенерировать"**.
2. Скачайте **Service Token**.

   * ⚠️ **Токен показывается только один раз!** Сохраните его в безопасное место.

Подробнее читайте в статье: [Служебные пользователи](ServiceUsers.md)

---

## **3. Получение Access Token (авторизация в API)**

Для работы с API HubEx нужен **JWT-токен доступа**, который обновляется каждые **30 минут**.

### **Запрос на получение Access Token**

**Метод:** `POST`
**URL:** `https://api.hubex.ru/fsm/AUTHZ/AccessTokens`

**Заголовки (`Headers`):**

```
Content-Type: application/json
```

**Тело запроса (`Body`):**

```
{
  "serviceToken": "ваш_сервисный_токен"
}
```

**Пример ответа (200 OK):**

```
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

* **`access_token`** — используйте его в каждом запросе.

---

## **4. Отправка первого API-запроса**

Теперь можно делать запросы к HubEx, добавляя **Access Token** в заголовки.

### **Пример: Получение списка заявок**

**Метод:** `GET`
**URL:** `https://api.hubex.ru/fsm/WORK/Tasks`

**Заголовки:**

```
Authorization: Bearer ваш_access_token
Content-Type: application/json
X-Application-ID: 5
```

**Параметры (опционально):**

```
?fetch=50         // Количество записей
&isClosed=false   // Только открытые заявки
&offset=0         // Пагинация
```

**Ответ (успешный):**

json

```
{
    "5136": {
        "isAvailable": true,
        "isRated": false,
        "sortOrder": 1,
        "lastModified": "2025-07-24T11:31:25",
        "workType": {
            "name": "Вид работ по умолчанию",
            "id": 2
        },
        "number": "000000001",
        "actualCriticality": { … },
        "taskStatus": { … },
        "taskType": { … },
        "requestedBy": { … },
        "company": { … },
        "asset": {
            "company": { … },
            "name": "Кондиционер",
            "id": 1020
        },
        "location": {
            "address": "Кирочная улица, 70, Санкт-Петербург, Россия",
            "coordinate": "59.939824:30.391287",
            "id": 5957
        },
        "timesheet": { … },
        "isFavourite": false,
        "taskStage": { … },
        "childCount": 0
    },
    "5135": {
        "isAvailable": true,
        "isRated": false,
        "sortOrder": 1,
        "lastModified": "2025-07-23T13:13:24",
        "workType": {
            "name": "Вид работ по умолчанию",
            "id": 2
        },
        "number": "000000002",
        "actualCriticality": { … },
        "taskStatus": { … },
        "taskType": { … },
        "requestedBy": { … },
        "company": { … },
        "asset": {
            "company": { … },
            "name": "Холодильник",
            "id": 1021
        },
        "location": {
            "address": "Смоляная улица, 23, Санкт-Петербург, Россия",
            "coordinate": "57.154824:28.254287",
            "id": 5845
        },
        "timesheet": { … },
        "isFavourite": false,
        "taskStage": { … },
        "childCount": 0
    }
}
```

---

## **5. Тестирование API (Postman, cURL, Python)**

### **Вариант 1: Postman**

1. Создайте новый запрос (`+ New → HTTP Request`).
2. Укажите:

   * **Метод:** `POST`
   * **URL:** `https://api.hubex.ru/fsm/AUTHZ/AccessTokens`
   * **Headers:** `Content-Type: application/json`
   * **Body (raw JSON):**

     ```
     {"serviceToken": "ваш_токен"}
     ```
3. Отправьте запрос и сохраните `access_token`.
4. Теперь делайте запросы к другим endpoint’ам, добавляя заголовок:

   ```
   Authorization: Bearer ваш_access_token
   ```

### **Вариант 2: cURL (командная строка)**

```
# Получение токена
curl -X POST "https://api.hubex.ru/fsm/AUTHZ/AccessTokens" \
     -H "Content-Type: application/json" \
     -d '{"serviceToken": "ваш_токен"}'
# Получение списка заявок
curl -X GET "https://api.hubex.ru/fsm/WORK/Tasks" \
     -H "Authorization: Bearer ваш_access_token" \
     -H "Content-Type: application/json"
```

### **Вариант 3: Python (requests)**

```
import requests
# 1. Получение токена
auth_url = "https://api.hubex.ru/fsm/AUTHZ/AccessTokens"
headers = {"Content-Type": "application/json"}
data = {"serviceToken": "ваш_токен"}
response = requests.post(auth_url, json=data, headers=headers)
access_token = response.json()["access_token"]
# 2. Запрос данных
tasks_url = "https://api.hubex.ru/fsm/WORK/Tasks"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
response = requests.get(tasks_url, headers=headers)
print(response.json())
```

---

## **6. Что делать дальше?**

1. **Изучите документацию API** — какие endpoints доступны:

   * [AUTHN](https://doc.hubex.ru/?urls.primaryName=AUTHN) – сервис для аутентификация учетных записей
   * [AUTHZ](https://doc.hubex.ru/?urls.primaryName=AUTHZ) – сервис для авторизации пользователей
   * [AUTH](https://doc.hubex.ru/?urls.primaryName=AUTH) – сервис для работы с учетной записью и авторизационными данными
   * [ADM](https://doc.hubex.ru/?urls.primaryName=ADM) – сервис для работы с данными пользователей и администрированием
   * [ES](https://doc.hubex.ru/?urls.primaryName=ES) – сервис для работы с компаниями, объектами, организационной структуры, локаций и т.п.
   * [PA](https://doc.hubex.ru/?urls.primaryName=PA) – сервис для управления персоналом - трудоустройство, назначение на оборудование, рейтинги, навыки и т.п.
   * [WORK](https://doc.hubex.ru/?urls.primaryName=WORK) – сервис для работы с заявками - список заявок, основные атрибуты по заявкам (чек-листы, выполнение и т.п.), создание заявок, вложения, назначения сотрудников и т.п.
   * [WSP](https://doc.hubex.ru/?urls.primaryName=WSP) – сервис для работы с графиками рабочего времени
   * [COMMON](https://doc.hubex.ru/?urls.primaryName=COMMON) – сервис для работы со справочниками: валюты, временные зоны, единицы измерения, дополнительные поля и т.п.
   * [SLA](https://doc.hubex.ru/?urls.primaryName=SLA) – сервис для работы с критичностью заявки и SLA
   * [TSTG](https://doc.hubex.ru/?urls.primaryName=TSTG) – сервис настройки жизненного цикла заявки
   * [UI](https://doc.hubex.ru/?urls.primaryName=UI) – сервис настройки пользовательского интерфейса
   * [EXPORT](https://doc.hubex.ru/?urls.primaryName=EXPORT) – сервис для экспорта данных
   * [PMP](https://doc.hubex.ru/?urls.primaryName=PMP) – сервис для работы с планировщиком работ
   * [MSG](https://doc.hubex.ru/?urls.primaryName=MSG) – сервис для работы с уведомлениями, Webhook, триггерами
   * [NEWS](https://doc.hubex.ru/?urls.primaryName=NEWS) – сервис по оповещению пользователей по обновлениям системы
   * [WH](https://doc.hubex.ru/?urls.primaryName=WH) – сервис для работы со складами и материалами
2. **Настройте обработку ошибок** (например, истечение токена).
3. **Реализуйте автоматическое обновление токена** (если интеграция долгосрочная).
4. **Настройте вебхуки** (если нужно получать уведомления от HubEx).

---

### **Готово!** 🎉

Теперь вы можете интегрировать HubEx с CRM, 1С, Telegram-ботами и другими системами. Если возникнут вопросы — обратитесь в поддержку HubEx.

---

### Следующие шаги:

* [Примеры API запросов в HubEx для реализации интеграции](ExampleRequestsAPI.md)

---

* [Перейти в меню](http://wiki.hubex.ru)
