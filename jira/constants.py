"""Shared validation constants for jira app."""
MIN_CONNECTION_NAME_LENGTH = 1
MAX_CONNECTION_NAME_LENGTH = 255
MAX_PROJECT_KEY_LENGTH = 64
MAX_BOARD_ID_LENGTH = 64
MAX_BASE_URL_LENGTH = 512

PROJECT_KEY_PATTERN = r"^[A-Z][A-Z0-9_]*$"

JIRA_MYSELF_PATH = "/rest/api/3/myself"
JIRA_PROJECT_PATH = "/rest/api/3/project/{project_key}"
JIRA_ISSUE_TYPES_PATH = "/rest/api/3/issuetype"
JIRA_FIELDS_PATH = "/rest/api/3/field"
JIRA_PRIORITIES_PATH = "/rest/api/3/priority"
JIRA_PROJECT_STATUSES_PATH = "/rest/api/3/project/{project_key}/statuses"
JIRA_PROJECT_COMPONENTS_PATH = "/rest/api/3/project/{project_key}/components"
JIRA_LABELS_PATH = "/rest/api/3/label"
JIRA_CREATE_META_PATH = "/rest/api/3/issue/createmeta"
JIRA_AGILE_BOARDS_PATH = "/rest/agile/1.0/board"
JIRA_AGILE_BOARD_SPRINTS_PATH = "/rest/agile/1.0/board/{board_id}/sprint"

JIRA_REQUEST_TIMEOUT_SECONDS = 15.0
JIRA_TEST_MAX_RETRIES = 3
JIRA_METADATA_MAX_RETRIES = 3
JIRA_METADATA_DEFAULT_TTL_SECONDS = 3600
JIRA_LABELS_PAGE_SIZE = 1000

# Jira schema.type / custom → normalized type for import templates
JIRA_SCHEMA_TYPE_TO_TEMPLATE = {
    "string": "text",
    "number": "number",
    "date": "date",
    "datetime": "datetime",
    "user": "user",
    "option": "select",
    "array": "multiselect",
    "priority": "priority",
    "status": "status",
    "project": "project",
    "issuetype": "issuetype",
    "timetracking": "timetracking",
    "any": "text",
}

JIRA_CUSTOM_TYPE_TO_TEMPLATE = {
    "com.atlassian.jira.plugin.system.customfieldtypes:textfield": "text",
    "com.atlassian.jira.plugin.system.customfieldtypes:textarea": "textarea",
    "com.atlassian.jira.plugin.system.customfieldtypes:float": "number",
    "com.atlassian.jira.plugin.system.customfieldtypes:datepicker": "date",
    "com.atlassian.jira.plugin.system.customfieldtypes:datetime": "datetime",
    "com.atlassian.jira.plugin.system.customfieldtypes:select": "select",
    "com.atlassian.jira.plugin.system.customfieldtypes:multiselect": "multiselect",
    "com.atlassian.jira.plugin.system.customfieldtypes:cascadingselect": "cascading_select",
    "com.atlassian.jira.plugin.system.customfieldtypes:labels": "labels",
    "com.atlassian.jira.plugin.system.customfieldtypes:userpicker": "user",
    "com.atlassian.jira.plugin.system.customfieldtypes:multiuserpicker": "multiselect_user",
    "com.atlassian.jira.plugin.system.customfieldtypes:url": "url",
    "com.atlassian.jira.plugin.system.customfieldtypes:readonlyfield": "readonly",
    "com.atlassian.jira.plugin.system.customfieldtypes:project": "project",
    "com.atlassian.jira.plugin.system.customfieldtypes:grouppicker": "group",
    "com.atlassian.jira.plugin.system.customfieldtypes:multicheckboxes": "multiselect",
    "com.atlassian.jira.plugin.system.customfieldtypes:radiobuttons": "select",
    "com.atlassian.jira.plugin.system.customfieldtypes:importid": "text",
    "com.atlassian.jira.plugin.system.customfieldtypes:version": "version",
    "com.atlassian.jira.plugin.system.customfieldtypes:multiversion": "multiselect_version",
}
