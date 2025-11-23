# tms/views/auth.py → ALREADY PERFECT
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

@login_required
def login_redirect(request):
    if request.user.is_superuser:
        return redirect('super_dashboard')
    elif hasattr(request.user, 'storeadmin'):
        return redirect('store_dashboard')
    else:
        return redirect('home')