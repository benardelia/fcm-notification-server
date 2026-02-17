import re
import logging

logger = logging.getLogger(__name__)


def render_template(template_string, variables):
    """
    Render a notification template string with variable substitution.

    Supports {{variable_name}} syntax.

    Examples:
        render_template("Hello {{name}}", {"name": "John"})
        => "Hello John"

        render_template("Order #{{order_id}} is {{status}}", {"order_id": "1234", "status": "ready"})
        => "Order #1234 is ready"

    Unresolved variables are left as-is: "Hello {{unknown}}" => "Hello {{unknown}}"
    """
    def replacer(match):
        key = match.group(1).strip()
        value = variables.get(key)
        if value is not None:
            return str(value)
        logger.warning(f"Template variable '{key}' not found in provided variables")
        return match.group(0)  # Leave unresolved

    return re.sub(r'\{\{(\s*\w+\s*)\}\}', replacer, template_string)


def render_notification_template(template, variables=None):
    """
    Render a NotificationTemplate model instance with the given variables.

    Args:
        template: NotificationTemplate model instance
        variables: Dict of variables to substitute into the template

    Returns:
        Dict with 'title', 'body', and 'data' ready to send
    """
    vars_dict = variables or {}

    title = render_template(template.title_template, vars_dict)
    body = render_template(template.body_template, vars_dict)

    # Merge default_data with any variable overrides
    data = {**template.default_data}
    # Also render template variables inside data values
    for key, value in data.items():
        if isinstance(value, str):
            data[key] = render_template(value, vars_dict)

    return {
        'title': title,
        'body': body,
        'data': data,
        'platform_overrides': template.platform_overrides,
    }
