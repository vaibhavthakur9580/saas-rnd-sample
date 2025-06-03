from django.http import HttpResponse
import pathlib
from django.shortcuts import render

# import the model to the main views page of our project to use it in views. 
from visits.models import PageVisits

# the line below is used to get the path of the file. the reason why this is better than providing absolute path is that this can get us the correct path regardless of where we runthis script from. 
# This guarantees your path is correct regardless of where you run the script from, because you’re telling Python to use the location of the script itself as a base.
# we dont need to hadrcode the path here. 
# we can dynamically get the path regardless of where the project is located or run from 
this_dir = pathlib.Path(__file__).resolve().parent

def home_page_view(request, *args, **kwargs):
    # get the data present inside the model so that we can use that data at other places. this data can also be manipulated at different places in our project and can also be prsented in the html files. 
    qs = PageVisits.objects.all()
    page_qs = PageVisits.objects.filter(path = request.path)
    # just a simple variable 
    my_title = "My Page"
    # just a dictionary containing the key value pairs which we can use at different places 
    my_context = {
        "page_title" : my_title,
        "page_visits_count" : page_qs.count(),
        "percent_count" : (page_qs.count() / qs.count()) * 100,
        "total_visit_count" : qs.count()
    }
    html_template = "home.html"
    path = request.path
    PageVisits.objects.create(path=request.path)

    return render(request, html_template, my_context)

def my_old_home_page_view(request, *args, **kwargs):
    # attach the html file we want to send to the user-in resonse to the users request-to the current directory path to get the complete path to the html file dynamically. 
    # html_file_path = this_dir / "home.html"
    # read the text present in the file 
    # html_ = html_file_path.read_text()
    # send the contents of the file to the user. 

    my_title = "My Page"
    my_context = {
        "page_title" : my_title
    }
    html_ = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>
<body>
    <h1>{page_title} anything? </h1>
</body>
</html>
""".format(**my_context)
    return HttpResponse(html_)