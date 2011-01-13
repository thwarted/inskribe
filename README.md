# Inskribe

Simple python templating library based on string.Formatter.

## Sample

Super simple sample that does not show all the features:

    import Inskribe

    class ShoppingList(Inskribe.Template):
        """
    Shopping List:
    {items|GroceryItemList}
    """

    class GroceryItemList(Inskribe.ListTemplate):
        """  {#:02d}. {name}
    """

    itemstobuy = [{'name': 'carrots'},
                  {'name': 'celery'},
                  {'name': 'potatoes'},
                  {'name': 'milk'},
                  {'name': 'eggs'},
                  {'name': 'cheese'}]
                                                                                                                                                            
    print ShoppingList(items=itemstobuy)


