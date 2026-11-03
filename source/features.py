OPTIONS = (
    ('tabs', 'ChatGPT / Codex tabs'),
    ('hide_gpt_projects', 'Hide projects in ChatGPT'),
    ('separate_recents', 'Separate recent chats'),
    ('floating_chat', 'Temporary floating chat'),
    ('bug_fixes', 'Bug fixes'),
)


def normalize(values=None, tabs=True):
    result = {key: False for key, label in OPTIONS}
    result['tabs'] = bool(tabs)
    if values is not None:
        if set(values) - result.keys(): raise ValueError('Unknown customization')
        result.update({key: bool(value) for key, value in values.items()})
    return result
