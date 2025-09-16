from django.shortcuts import render
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from movies.models import Movie
from .utils import calculate_cart_total
from .models import Order, Item
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone
import json
import os

def index(request):
    cart_total = 0
    movies_in_cart = []
    cart = request.session.get('cart', {})
    movie_ids = list(cart.keys())
    if (movie_ids != []):
        movies_in_cart = Movie.objects.filter(id__in=movie_ids)
        cart_total = calculate_cart_total(cart, movies_in_cart)

    template_data = {}
    template_data['title'] = 'Cart'
    template_data['movies_in_cart'] = movies_in_cart
    template_data['cart_total'] = cart_total
    return render(request, 'cart/index.html', {'template_data': template_data})

def add(request, id):
    get_object_or_404(Movie, id=id)
    cart = request.session.get('cart', {})
    cart[id] = request.POST['quantity']
    request.session['cart'] = cart
    return redirect('cart.index')

def clear(request):
    request.session['cart'] = {}
    return redirect('cart.index')

@login_required
def purchase(request):
    cart = request.session.get('cart', {})
    movie_ids = list(cart.keys())

    if (movie_ids == []):
        return redirect('cart.index')
    
    movies_in_cart = Movie.objects.filter(id__in=movie_ids)
    cart_total = calculate_cart_total(cart, movies_in_cart)

    order = Order()
    order.user = request.user
    order.total = cart_total
    order.save()

    for movie in movies_in_cart:
        item = Item()
        item.movie = movie
        item.price = movie.price
        item.order = order
        item.quantity = cart[str(movie.id)]
        item.save()

    request.session['cart'] = {}
    template_data = {}
    template_data['title'] = 'Purchase confirmation'
    template_data['order_id'] = order.id
    template_data['order'] = order
    return render(request, 'cart/purchase.html', {'template_data': template_data})

# --- Simple file-backed feedback (no DB, no migrations) ---
@csrf_exempt
@require_POST
def submit_feedback(request):
    try:
        data = json.loads(request.body)
        name = (data.get('name') or '').strip()
        thoughts = (data.get('thoughts') or '').strip()
        if not thoughts:
            return JsonResponse({'success': False, 'error': 'Thoughts field is required'})

        feedback_dir = os.path.join(settings.MEDIA_ROOT, 'feedback')
        os.makedirs(feedback_dir, exist_ok=True)
        file_path = os.path.join(feedback_dir, 'feedback.jsonl')
        entry = {
            'name': name if name else None,
            'thoughts': thoughts,
            'date': timezone.now().isoformat()
        }
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        return JsonResponse({'success': True, 'message': 'Thank you for your feedback!'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception:
        return JsonResponse({'success': False, 'error': 'An error occurred while saving feedback'})

def feedback_list(request):
    feedbacks = []
    file_path = os.path.join(settings.MEDIA_ROOT, 'feedback', 'feedback.jsonl')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    feedbacks.append(json.loads(line))
                except Exception:
                    continue
        feedbacks.sort(key=lambda x: x.get('date', ''), reverse=True)
    template_data = {
        'title': 'Checkout Feedback',
        'feedbacks': feedbacks,
    }
    return render(request, 'cart/feedback.html', {'template_data': template_data})