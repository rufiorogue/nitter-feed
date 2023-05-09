from typing import Iterator


def _dict_hierarchy_squash(parent_category: str, branch: dict) -> Iterator[tuple(str,str)]:
    for k,v in branch.items():
        subcategory = parent_category + "/" + k
        if type(v) is dict:
            yield from _dict_hierarchy_squash(subcategory, v)
        else:
            for asset in v:
                yield asset,subcategory

def dict_hierarchy_squash(hierarchy: dict) -> Iterator[tuple(str,str)]:
    """
        hierarchy is a dict with dicts as values, like so:
        {
            'a': {
                'b': 'foo',
                'c': {
                    'd': 'bar'
                }
            }
        }
        
        result looks like this:
        [
            ('foo', 'a.b'),
            ('bar', 'a.c.d')
        ]

        An Iterator to list above is returned, instead of list directly


    """
    yield from _dict_hierarchy_squash('', hierarchy)
