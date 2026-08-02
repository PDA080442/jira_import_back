from django.db import migrations

GUIDE_SLUG = "jira-connection-setup"

GUIDE_CONTENT = [
    {
        "id": "intro",
        "title": "1. Что это за страница и зачем она нужна",
        "blocks": [
            {
                "type": "paragraph",
                "text": (
                    "На странице «Подключения Jira» вы связываете свой рабочий "
                    "workspace с конкретным проектом в Jira Cloud. После подключения "
                    "сервис сможет читать метаданные проекта (типы задач, поля, "
                    "приоритеты, статусы, компоненты, метки, доски и спринты) и позже "
                    "публиковать в Jira импортированные задачи."
                ),
            },
            {
                "type": "paragraph",
                "text": (
                    "Одно подключение = один проект Jira. Внутри workspace можно "
                    "создать несколько подключений, если вы работаете с несколькими "
                    "проектами."
                ),
            },
            {
                "type": "note",
                "variant": "info",
                "text": (
                    "Подключение НЕ удаляется полностью — его можно только "
                    "«деактивировать», чтобы сохранить историю действий."
                ),
            },
        ],
    },
    {
        "id": "prerequisites",
        "title": "2. Что нужно подготовить заранее",
        "blocks": [
            {
                "type": "list",
                "items": [
                    "Учётная запись в Jira Cloud (адрес вида your-company.atlassian.net).",
                    "Доступ к нужному проекту в Jira (вы должны видеть его задачи).",
                    "Роль admin или owner в текущем workspace — только они могут создавать и менять подключения.",
                    "Около 5 минут времени, чтобы создать API-токен в Atlassian.",
                ],
            },
            {
                "type": "note",
                "variant": "warning",
                "text": (
                    "Если у вас роль viewer или editor — вы увидите список подключений, "
                    "но кнопки создания и изменения будут недоступны. Попросите "
                    "администратора workspace."
                ),
            },
        ],
    },
    {
        "id": "site-url",
        "title": "3. Как узнать URL сайта Jira (поле «Base URL»)",
        "blocks": [
            {
                "type": "paragraph",
                "text": (
                    "Base URL — это адрес вашего сайта Jira Cloud. Его видно в адресной "
                    "строке браузера, когда вы открыли Jira."
                ),
            },
            {
                "type": "steps",
                "items": [
                    {"text": "Откройте Jira в браузере и войдите в свою учётную запись."},
                    {
                        "text": "Посмотрите на адресную строку — она выглядит как https://your-company.atlassian.net/...",
                        "hint": "Нужна часть до /jira или /browse.",
                    },
                    {
                        "text": "Скопируйте адрес вида https://your-company.atlassian.net — без слэша в конце и без пути.",
                    },
                ],
            },
            {
                "type": "note",
                "variant": "info",
                "text": "Пример правильного значения: https://acme.atlassian.net",
            },
        ],
    },
    {
        "id": "project-key",
        "title": "4. Как найти ключ проекта (поле «Project key»)",
        "blocks": [
            {
                "type": "paragraph",
                "text": (
                    "Ключ проекта — это короткий код проекта в Jira (обычно 2–10 "
                    "заглавных букв/цифр), например ACME, WEB, DEV."
                ),
            },
            {
                "type": "steps",
                "items": [
                    {"text": "В Jira откройте нужный проект (меню Projects → выберите проект)."},
                    {
                        "text": "Посмотрите на префикс задач: если задачи называются WEB-123, WEB-124 — то ключ проекта WEB.",
                        "hint": "Ключ также виден в URL: /browse/WEB-123.",
                    },
                    {"text": "Скопируйте ключ ровно так, как он написан (регистр важен, обычно ЗАГЛАВНЫМИ)."},
                ],
            },
        ],
    },
    {
        "id": "api-token",
        "title": "5. Как создать API-токен в Atlassian (поле «API token»)",
        "blocks": [
            {
                "type": "paragraph",
                "text": (
                    "API-токен заменяет пароль при обращении к Jira по API. Мы храним "
                    "его в зашифрованном виде и НИКОГДА не возвращаем обратно в ответах."
                ),
            },
            {
                "type": "steps",
                "items": [
                    {
                        "text": "Откройте страницу управления токенами Atlassian.",
                        "hint": "https://id.atlassian.com/manage-profile/security/api-tokens",
                    },
                    {"text": "Нажмите кнопку «Create API token» (Создать API-токен)."},
                    {
                        "text": "Введите понятное имя, например «Jira Import Service», и подтвердите.",
                        "hint": "Имя нужно только вам, чтобы отличать токены.",
                    },
                    {
                        "text": "Скопируйте показанный токен СРАЗУ — после закрытия окна его больше нельзя посмотреть.",
                    },
                    {"text": "Вставьте токен в поле «API token» на нашей странице подключений."},
                ],
            },
            {
                "type": "note",
                "variant": "warning",
                "text": (
                    "Никому не пересылайте токен и не храните его в открытых заметках. "
                    "Если токен утёк — отзовите его в Atlassian и создайте новый."
                ),
            },
            {
                "type": "link",
                "text": "Создать API-токен Atlassian",
                "url": "https://id.atlassian.com/manage-profile/security/api-tokens",
            },
        ],
    },
    {
        "id": "email",
        "title": "6. Какой email указывать (поле «Email»)",
        "blocks": [
            {
                "type": "paragraph",
                "text": (
                    "Укажите email той учётной записи Atlassian, для которой вы создали "
                    "API-токен. Пара email + токен используется для авторизации в Jira."
                ),
            },
            {
                "type": "note",
                "variant": "info",
                "text": (
                    "Токен привязан к конкретному пользователю. Все действия сервиса в "
                    "Jira будут выполняться от имени этого пользователя, поэтому у него "
                    "должны быть права на проект."
                ),
            },
        ],
    },
    {
        "id": "board-id",
        "title": "7. Board ID для scrum/kanban (необязательно)",
        "blocks": [
            {
                "type": "paragraph",
                "text": (
                    "Если ваш проект использует доски (scrum/kanban) и вам нужны спринты, "
                    "можно указать ID доски. Это поле необязательное — без него "
                    "подключение всё равно работает."
                ),
            },
            {
                "type": "steps",
                "items": [
                    {"text": "Откройте доску проекта в Jira (Backlog или Board)."},
                    {
                        "text": "Посмотрите в URL: .../boards/42 — число 42 и есть Board ID.",
                        "hint": "rapidView=42 — тоже Board ID.",
                    },
                ],
            },
        ],
    },
    {
        "id": "fill-form",
        "title": "8. Заполнение формы подключения — по полям",
        "blocks": [
            {
                "type": "fields",
                "items": [
                    {
                        "name": "name",
                        "label": "Название",
                        "required": True,
                        "example": "Проект WEB (прод)",
                        "description": "Понятное вам имя подключения. Видно только внутри сервиса.",
                    },
                    {
                        "name": "base_url",
                        "label": "Base URL",
                        "required": True,
                        "example": "https://acme.atlassian.net",
                        "description": "Адрес сайта Jira Cloud без слэша в конце (см. пункт 3).",
                    },
                    {
                        "name": "email",
                        "label": "Email",
                        "required": True,
                        "example": "user@acme.com",
                        "description": "Email учётной записи, для которой создан API-токен (см. пункт 6).",
                    },
                    {
                        "name": "api_token",
                        "label": "API token",
                        "required": True,
                        "example": "ATATT3xFfGF0...",
                        "description": "Токен из Atlassian (см. пункт 5). Хранится зашифрованно, в ответах не возвращается.",
                    },
                    {
                        "name": "project_key",
                        "label": "Project key",
                        "required": True,
                        "example": "WEB",
                        "description": "Ключ проекта в Jira (см. пункт 4). Регистр важен.",
                    },
                    {
                        "name": "board_id",
                        "label": "Board ID",
                        "required": False,
                        "example": "42",
                        "description": "ID доски для scrum/kanban (см. пункт 7). Можно оставить пустым.",
                    },
                ],
            },
            {
                "type": "note",
                "variant": "info",
                "text": (
                    "После сохранения поле с токеном всегда будет пустым в ответах API — "
                    "это защита. Чтобы сменить токен, просто введите новый и сохраните."
                ),
            },
        ],
    },
    {
        "id": "test-connection",
        "title": "9. Проверка подключения (кнопка «Проверить»)",
        "blocks": [
            {
                "type": "paragraph",
                "text": (
                    "После сохранения нажмите «Проверить». Сервис обратится к Jira с "
                    "вашими данными и покажет результат."
                ),
            },
            {
                "type": "list",
                "items": [
                    "success — данные верны, проект доступен. Можно синхронизировать метаданные.",
                    "failed — что-то не так: неверный email/токен, нет доступа к проекту или неправильный Base URL.",
                ],
            },
            {
                "type": "note",
                "variant": "info",
                "text": "Результат последней проверки сохраняется и виден в карточке подключения.",
            },
        ],
    },
    {
        "id": "sync-metadata",
        "title": "10. Синхронизация метаданных проекта",
        "blocks": [
            {
                "type": "paragraph",
                "text": (
                    "Когда подключение проверено, запустите синхронизацию — сервис "
                    "загрузит из Jira типы задач, поля, приоритеты, статусы, компоненты, "
                    "метки, а также доски и спринты."
                ),
            },
            {
                "type": "steps",
                "items": [
                    {"text": "Нажмите «Синхронизировать метаданные» — статус станет syncing."},
                    {"text": "Дождитесь статуса fresh (обычно несколько секунд)."},
                    {
                        "text": "Если статус стал failed — откройте детали ошибки и проверьте токен/доступ, затем повторите.",
                    },
                ],
            },
            {
                "type": "note",
                "variant": "info",
                "text": (
                    "Метаданные кэшируются с TTL. Когда они устаревают, поле is_stale "
                    "становится true — просто запустите синхронизацию заново."
                ),
            },
        ],
    },
    {
        "id": "roles",
        "title": "11. Кто и что может делать",
        "blocks": [
            {
                "type": "list",
                "items": [
                    "viewer / editor — видят список подключений и метаданные, но не могут создавать/менять/синхронизировать.",
                    "admin / owner — создают, редактируют, деактивируют подключения и запускают синхронизацию.",
                ],
            },
        ],
    },
    {
        "id": "security",
        "title": "12. Безопасность",
        "blocks": [
            {
                "type": "list",
                "items": [
                    "API-токен хранится в БД в зашифрованном виде.",
                    "Токен никогда не возвращается в ответах API и не пишется в логи.",
                    "Все действия с подключениями фиксируются в аудите (кто и когда).",
                    "При утечке токена отзовите его в Atlassian и введите новый в форме.",
                ],
            },
        ],
    },
    {
        "id": "troubleshooting",
        "title": "13. Типичные проблемы и решения",
        "blocks": [
            {
                "type": "fields",
                "items": [
                    {
                        "name": "401 / INVALID_CREDENTIALS",
                        "label": "Не проходит авторизация",
                        "required": False,
                        "example": "",
                        "description": "Проверьте пару email + API-токен. Токен мог быть отозван — создайте новый.",
                    },
                    {
                        "name": "403 / FORBIDDEN",
                        "label": "Нет прав на проект",
                        "required": False,
                        "example": "",
                        "description": "У пользователя нет доступа к проекту в Jira. Проверьте права в Jira.",
                    },
                    {
                        "name": "404 / NOT_FOUND",
                        "label": "Проект не найден",
                        "required": False,
                        "example": "",
                        "description": "Неверный Project key или Base URL. Сверьте ключ и адрес сайта.",
                    },
                    {
                        "name": "429 / RATE_LIMIT",
                        "label": "Слишком много запросов",
                        "required": False,
                        "example": "",
                        "description": "Jira временно ограничила запросы. Подождите и повторите синхронизацию позже.",
                    },
                ],
            },
        ],
    },
]


def seed_guide(apps, schema_editor):
    JiraGuide = apps.get_model("jira", "JiraGuide")
    JiraGuide.objects.update_or_create(
        slug=GUIDE_SLUG,
        defaults={
            "title": "Подключение Jira Cloud: пошаговая инструкция",
            "summary": (
                "Как получить Base URL, project key и API-токен и подключить проект "
                "Jira к workspace, проверить подключение и синхронизировать метаданные."
            ),
            "locale": "ru",
            "content": GUIDE_CONTENT,
            "version": 1,
            "is_published": True,
        },
    )


def unseed_guide(apps, schema_editor):
    JiraGuide = apps.get_model("jira", "JiraGuide")
    JiraGuide.objects.filter(slug=GUIDE_SLUG).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("jira", "0003_jiraguide"),
    ]

    operations = [
        migrations.RunPython(seed_guide, unseed_guide),
    ]
