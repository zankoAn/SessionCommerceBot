from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('bot/', include('ecommerce.bot.urls')),

    # path('payment/', include('ecommerce.payment.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
