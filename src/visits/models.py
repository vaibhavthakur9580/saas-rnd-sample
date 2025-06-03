from django.db import models

# Create your models here.

# below we have defined a model for our app visits, that acts as a table which has columns that we can define. this can store the data for the app and we can then use this model to use the data where we want such as in the html files as templates. 
class PageVisits(models.Model):
    # these two are both columns and they both map to a database table
    # db -> table 
    # id -> hidden -> primary key -> autofield -> 1,2,3,3,4
    path = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)  
