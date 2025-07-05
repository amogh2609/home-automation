from django.urls import path
from .views import RoomListCreateView,RoomRetrieveUpdateDeleteView,SlaveDeviceListCreateView,ApplianceUsageLogListView,SlaveDeviceRetrieveUpdateDeleteView,ApplianceListCreateView,ApplianceRetrieveUpdateDeleteView

urlpatterns = [
    path('rooms/', RoomListCreateView.as_view(), name='room-list-create'),
    path('rooms/<int:pk>/', RoomRetrieveUpdateDeleteView.as_view(), name='room-rud'),
    path('slave-devices/', SlaveDeviceListCreateView.as_view(), name='slave-list-create'),
    path('slave-devices/<int:id>/', SlaveDeviceRetrieveUpdateDeleteView.as_view(), name='slave-rud'),
    path('appliances/', ApplianceListCreateView.as_view(), name='appliance-list-create'),
    path('appliances/<int:id>/', ApplianceRetrieveUpdateDeleteView.as_view(), name='appliance-rud'),
    path('appliance-logs/', ApplianceUsageLogListView.as_view(), name='appliance-usage-log-list'),

]