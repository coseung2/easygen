"""Names scoped to each user's own workflow, separate from the maintainer app."""
import os
import re


def resource(suffix):
    prefix = os.environ.get('EASYGEN_WORKFLOW_PREFIX', 'my-workflow')
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', prefix):
        raise ValueError('EASYGEN_WORKFLOW_PREFIX: use 1-40 lowercase letters/digits/hyphens, starting with a letter')
    return f'{prefix}-{suffix}'
