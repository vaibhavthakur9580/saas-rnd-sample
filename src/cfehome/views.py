from django.http import HttpResponse
import pathlib
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
LOGIN_URL = settings.LOGIN_URL

from visits.models import PageVisits


this_dir = pathlib.Path(__file__).resolve().parent

def home_view(request, *args, **kwargs):
    if request.user.is_authenticated:
        print(request.user.is_authenticated, request.user)
    return about_view(request, *args, **kwargs)


def about_view(request,  *args, **kwargs):
    qs = PageVisits.objects.all()
    page_qs = PageVisits.objects.filter(path = request.path)
    try: 
        percent = (page_qs.count() / qs.count()) * 100
    except:
        percent = 0
    my_title = "My Page"
    my_context = {
        "page_title" : my_title,
        "page_visits_count" : page_qs.count(),
        "percent_count" : percent,
        "total_visit_count" : qs.count()
    }
    html_template = "home.html"
    path = request.path
    PageVisits.objects.create(path=request.path)
    return render(request, html_template, my_context)

def my_old_home_page_view(request, *args, **kwargs):
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


VALID_CODE = "abc123"

def pw_protected_view(request, *args, **kwargs):
    is_allowed = request.session.get('protected_page_allowed') or 0
    print(request.session.get('protected_page_allowed'), type(request.session.get('protected_page_allowed')))
    if request.method == 'POST':
        user_pw_sent = request.POST.get('code') or None
        if user_pw_sent == VALID_CODE:
            is_allowed = 1
            request.session['protected_page_allowed'] = is_allowed
    if is_allowed:
        return render(request, "protected/view.html", {})
    return render(request, "protected/entry.html", {})

@login_required(login_url=LOGIN_URL)
def user_only_view(request, *args, **kwargs):
    # print(request.user.is_staff)
    return render(request, "protected/user-only.html", {})

@staff_member_required(login_url=LOGIN_URL)
def staff_only_view(request, *args, **kwargs):
    return render(request, "protected/user-only.html", {})

