from django.shortcuts import render
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from core.models import User,Room,Appliance,ApplianceUsageLog,Controller,SlaveDevice
from .serializers import UserSerializer,RoomSerializer,SlaveDeviceSerializer,RoomUpdateSerializer,ApplianceUsageLogSerializer,ApplianceSerializer,RoomaAplienceSerializer
from django.contrib.auth.models import Group
from rest_framework.exceptions import PermissionDenied
from rest_framework import generics
from rest_framework.request import Request
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.response import Response

class AdminCreateUserView(CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        if not user.groups.filter(name='admin').exists():
            raise PermissionDenied("Only admins can create users through this endpoint.")
        serializer.save()
        
class HomeownerCreateFamilyUserView(CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        if not user.groups.filter(name='homeowner').exists():
            raise PermissionDenied("Only homeowners can create family users.")
        serializer.save()

class RoomListCreateView(generics.ListCreateAPIView):
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        customer_id = self.request.query_params.get("homeowner")

        if user.groups.filter(name='technician').exists() or user.groups.filter(name='admin').exists():
            if customer_id:
                return Room.objects.filter(homeowner__id=customer_id)
            return Room.objects.all()

        elif user.groups.filter(name='homeowner').exists():
            return Room.objects.filter(homeowner=user)
        
        elif user.homeowner:  # Family member
            return Room.objects.filter(homeowner=user.homeowner)
        return Room.objects.none()

    def perform_create(self, serializer):
        user = self.request.user

        # ✅ 1. Only technicians can create rooms
        if not user.groups.filter(name='technician').exists():
            raise PermissionDenied("Only technicians can create rooms.")
        
        controller_id = self.request.data.get('controller')
        try:
            controller = Controller.objects.get(id=controller_id)
        except Controller.DoesNotExist:
            raise ValidationError("Invalid controller ID.")

        homeowner = controller.homeowner

        # ✅ 5. Save room with validated data
        serializer.save(
            controller=controller,
            homeowner=homeowner,
        )
        
class RoomRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.groups.filter(name='technician').exists() or user.groups.filter(name='admin').exists():
            return Room.objects.select_related('homeowner', 'controller').all()

        elif user.groups.filter(name='homeowner').exists():
            return Room.objects.filter(homeowner=user).select_related('controller')

        elif user.homeowner:  # family member
            return Room.objects.filter(homeowner=user.homeowner).select_related('controller')

        return Room.objects.none()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return RoomUpdateSerializer
        return RoomaAplienceSerializer

    def retrieve(self, request, *args, **kwargs):
        """
        Return room + nested appliances if user is homeowner or family
        """
        room = self.get_object()
        serializer = self.get_serializer(room)
        return Response(serializer.data)

    def perform_update(self, serializer):
        user = self.request.user

        if not user.groups.filter(name='technician').exists():
            raise PermissionDenied("Only technicians can update rooms.")

        # Ensure only 'name' is being updated
        allowed_fields = {'name'}
        invalid_fields = [f for f in self.request.data.keys() if f not in allowed_fields]
        if invalid_fields:
            raise ValidationError(f"Only the 'name' field can be updated. Invalid fields: {invalid_fields}")

        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if not user.groups.filter(name='technician').exists():
            raise PermissionDenied("Only technicians can delete rooms.")
        instance.delete()
    
class SlaveDeviceListCreateView(generics.ListCreateAPIView):
    queryset = SlaveDevice.objects.all()
    serializer_class = SlaveDeviceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        if user.groups.filter(name='technician').exists():
            return SlaveDevice.objects.select_related('controller', 'room').all()
        
        elif user.groups.filter(name='homeowner').exists():
            return SlaveDevice.objects.filter(
                controller__homeowner=user
            ).select_related('controller', 'room')
        
        elif user.homeowner:  # Family member
            return SlaveDevice.objects.filter(
                controller__homeowner=user.homeowner
            ).select_related('controller', 'room')
        
        return SlaveDevice.objects.none()
    
    def perform_create(self, serializer):
        user = self.request.user
        if not user.groups.filter(name='technician').exists():
            raise PermissionDenied("Only technicians can create slave devices.")
        controller_id = self.request.data.get('controller')
        if controller_id:
            try:
                controller = Controller.objects.get(id=controller_id)
                # Check if controller has reached max slaves
                if controller.slaves.count() >= controller.max_slaves:
                    raise ValidationError(f"Controller has reached maximum slave capacity ({controller.max_slaves}).")
            except Controller.DoesNotExist:
                raise ValidationError("Invalid controller ID.")
        else:
            raise ValidationError("Controller is required.")
        serializer.save()


class SlaveDeviceRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SlaveDevice.objects.all()
    serializer_class = SlaveDeviceSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        user = self.request.user
        
        if user.groups.filter(name='technician').exists():
            return SlaveDevice.objects.select_related('controller', 'room').all()
        
        elif user.groups.filter(name='homeowner').exists():
            return SlaveDevice.objects.filter(
                controller__homeowner=user
            ).select_related('controller', 'room')
        
        elif user.homeowner:  # Family member (read-only)
            return SlaveDevice.objects.filter(
                controller__homeowner=user.homeowner
            ).select_related('controller', 'room')
        
        return SlaveDevice.objects.none()
    
    def perform_update(self, serializer):
        user = self.request.user
        if not user.groups.filter(name='technician').exists():
            raise PermissionDenied("Only technicians can update slave devices.")

        # Optional: restrict updatable fields
        allowed_fields = {'name', 'room'}
        invalid_fields = [f for f in self.request.data if f not in allowed_fields]
        if invalid_fields:
            raise ValidationError(f"Only 'name' and 'room' can be updated. Invalid fields: {invalid_fields}")

        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if not user.groups.filter(name='technician').exists():
            raise PermissionDenied("Only technicians can delete slave devices.")
        instance.delete()

class ApplianceListCreateView(generics.ListCreateAPIView):
    serializer_class = ApplianceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.groups.filter(name='technician').exists() or user.groups.filter(name='admin').exists() :
            return Appliance.objects.all()

        elif user.groups.filter(name='homeowner').exists():
            return Appliance.objects.filter(room__homeowner=user).select_related('room', 'slave')

        elif user.homeowner:
            return Appliance.objects.filter(room__homeowner=user.homeowner).select_related('room', 'slave')

        return Appliance.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if not user.groups.filter(name='technician').exists():
            raise PermissionDenied("Only technicians can create appliances.")
        room = serializer.validated_data.get('room')
        slave = serializer.validated_data.get('slave')
        channel = serializer.validated_data.get('channel')
        
        if slave and channel is not None:
            # Check if channel is already used by another appliance on the same slave
            if Appliance.objects.filter(slave=slave, channel=channel).exists():
                raise ValidationError(f"Channel {channel} is already in use on this slave device.")
        serializer.save()
        
class ApplianceRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ApplianceSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user

        if user.groups.filter(name='technician').exists():
            return Appliance.objects.select_related('room', 'slave').all()

        elif user.groups.filter(name='homeowner').exists():
            return Appliance.objects.filter(
                room__homeowner=user
            ).select_related('room', 'slave')

        elif user.homeowner:  # Family member
            return Appliance.objects.filter(
                room__homeowner=user.homeowner
            ).select_related('room', 'slave')
        
        return Appliance.objects.none()
    
    def perform_update(self, serializer):
        user = self.request.user
        if not user.groups.filter(name='technician').exists():
            raise PermissionDenied("Only technicians can update appliances.")
        instance = self.get_object()
        slave = serializer.validated_data.get('slave', instance.slave)
        channel = serializer.validated_data.get('channel', instance.channel)
        
        if slave and channel is not None:
            # Exclude current instance from conflict check
            if Appliance.objects.filter(slave=slave, channel=channel).exclude(id=instance.id).exists():
                raise ValidationError(f"Channel {channel} is already in use on this slave device.")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if not user.groups.filter(name='technician').exists():
            raise PermissionDenied("Only technicians can delete appliances.")
        instance.delete()     

class ApplianceUsageLogListView(generics.ListAPIView):
    queryset = ApplianceUsageLog.objects.all()
    serializer_class = ApplianceUsageLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.groups.filter(name='homeowner').exists():
            return ApplianceUsageLog.objects.filter(appliance__room__homeowner=user)
        return ApplianceUsageLog.objects.none()
