from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render, redirect
from django.views.generic import ListView
from django.conf import settings

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

from memberships.models import Membership, UserMembership, Subscription
# Create your views here.


def get_user_membership(request):
    user_membership_qs = UserMembership.objects.filter(user=request.user)
    if user_membership_qs.exists():
        return user_membership_qs.first()
    else:
        return None


def get_user_subscription(request):
    user_subscription_qs = Subscription.objects.filter(
        user_membership=get_user_membership(request)
    )
    if user_subscription_qs.exists():
        return user_subscription_qs.first()
    else:
        return None


def get_selected_membership(request):
    membership_type = request.session['selected_membership_type']
    selected_membership_qs = Membership.objects.filter(membership_type=membership_type)
    if selected_membership_qs.exists():
        return selected_membership_qs.first()
    else:
        return None

# Implement a instant upgrade logic to select view:
# 1. add a upgrade button next to select button
# 2. charge the upgrade fee according to the remaining days to expiration:
#     if remaining_days <= 7:
#         upgrade_fee = subscription_fee / 3
#     else if remaining days > 7 and remaining days <= 14:
#         upgrade_fee = subscription_fee / 2
#     else if remaining days > 14 and remaining days <= 21:
#         upgrade_fee = subscription_fee / 3 * 2
#     else if remaining days > 21 and remaining days <= 31:
#         upgrade_fee = subscription_fee
#     else:
#         handleException()

class MembershipSelectView(ListView):
    model = Membership

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        current_membership = get_user_membership(self.request)
        context['current_membership'] = current_membership.membership.membership_type
        return context

    def post(self, request, **kwargs):
        selected_membership_type = request.POST.get('membership_type')

        user_membership = get_user_membership(request)
        user_subscription = get_user_subscription(request)

        '''
        Validate if selected membership is not equal to user's membership
        '''
        selected_membership_qs = Membership.objects.filter(membership_type=selected_membership_type)
        if selected_membership_qs.exists():
            selected_membership = selected_membership_qs.first()

        if user_membership.membership == selected_membership:
            if user_subscription != None:
                messages.info(request, 'Your next payment is due {}.'.format(''))
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # store selected membership info for later use
        request.session['selected_membership_type'] = selected_membership.membership_type
        return HttpResponseRedirect(reverse('memberships:payment'))


def PaymentView(request):
    user_membership = get_user_membership(request)
    selected_membership = get_selected_membership(request)
    publish_key = settings.STRIPE_PUBLISHABLE_KEY

    if request.method == 'POST':
        try:
            token = request.POST.get('stripeToken')
            customer_id = user_membership.stripe_customer_id
            customer = stripe.Customer.retrieve(customer_id)
            stripe_token = stripe.Token.retrieve(token)
            card_id = stripe_token.card.id
            for card in customer.sources.list():
                if card.fingerprint == stripe_token.card.fingerprint:
                    card_exists = True
                    break
            if not card_exists:
                customer.sources.create(source=token)
                customer.save()

            subscription = stripe.Subscription.create(
              customer=customer_id,
              items=[
                {
                  "plan": selected_membership.stripe_plan_id,
                },
              ],
            )
            return redirect(reverse('memberships:update-transaction',
                                    kwargs={
                                        'subscription_id': subscription.id
                                    }))
        except stripe.error.CardError as e:
            messages.info(request, 'You card has been declined.')

    context = {
        "publish_key": publish_key,
        "selected_membership": selected_membership,
    }
    return render(request, 'memberships/membership_payment.html', context)


def updateTransaction(request, subscription_id):
    user_membership = get_user_membership(request)
    selected_membership = get_selected_membership(request)
    user_membership.membership = selected_membership
    user_membership.save()

    sub, created = Subscription.objects.get_or_create(user_membership=user_membership)
    sub.stripe_subscription_id = subscription_id
    sub.active = True
    sub.save()

    try:
        del request.session['selected_membership_type']
    except:
        pass
    messages.info(request, 'Successfully created {} membership'.format(selected_membership))
    return redirect(reverse('courses:list'))
