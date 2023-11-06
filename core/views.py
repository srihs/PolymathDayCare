from django.shortcuts import render
from .models import Child
from .forms import CreateChildForm


# Create your views here.
def index(request):
  
  return render(request, '../templates/base.html')


def getChild(request):
  # clearing the session form the system. so the New id will be facilitated
  request.session['child_id'] = None
  request.session.modified = True
  # Child is defined by 'D' + next Id in the Table
  try:
    # trying to retrive the next primaryKey
    nextId = Child.objects.all().count()
    nextId += 1
  except:
    nextId = 1  # if the next ID is null define the record as the first

  child_form = CreateChildForm(initial={'admission_number': 'D' + str(nextId)})  # creating the form with the admission ID

  return render(request, '../templates/child.html',{'form': CreateChildForm})
