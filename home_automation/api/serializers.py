from rest_framework import serializers
from core.models import Room, Appliance, ApplianceUsageLog,Controller,SlaveDevice
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(
        choices=['admin', 'homeowner', 'technician'],
        write_only=True,
        required=False
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'role']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        request = self.context['request']
        current_user = request.user
        input_role = validated_data.pop('role', None)
        raw_password = validated_data.pop('password')

        new_user = User(**validated_data)
        new_user.set_password(raw_password)

        if current_user.groups.filter(name='homeowner').exists():
            if current_user.family_members.count() >= 10:
                raise serializers.ValidationError("You can only add up to 10 family members.")
            family_group = Group.objects.get(name='family')
            new_user.homeowner = current_user
            new_user.save()
            new_user.groups.add(family_group)

        elif current_user.groups.filter(name='admin').exists():
            if not input_role:
                raise serializers.ValidationError("Admin must assign a role.")
            target_group = Group.objects.get(name=input_role)
            new_user.save()
            new_user.groups.add(target_group)

        else:
            raise serializers.ValidationError("You do not have permission to create users.")

        return new_user
    
class RoomUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['name']

class ControllerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Controller
        fields = ['id', 'mac_address', 'homeowner']

    def validate_homeowner(self, user):
        if not user.groups.filter(name='homeowner').exists():
            raise serializers.ValidationError("Only users in the 'homeowner' group can own a controller.")
        return user

class ApplianceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appliance
        fields = '__all__'

    def validate(self, data):
        room = data.get('room')
        slave = data.get('slave')

        if slave and room and room.homeowner != slave.controller.homeowner:
            raise serializers.ValidationError(
                "Slave device does not belong to the same homeowner as the room."
            )
        return data
class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'name', 'controller', 'homeowner']
        read_only_fields = ['controller', 'homeowner']

class RoomaAplienceSerializer(serializers.ModelSerializer):
    appliances = ApplianceSerializer(many=True, read_only=True, source = "appliance_set")

    class Meta:
        model = Room
        fields = ['id', 'name', 'controller', 'homeowner', 'appliances']
        read_only_fields = ['controller', 'homeowner']
        
class ApplianceUsageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplianceUsageLog
        fields = '__all__'

    def validate(self, data):
        start_time = data.get('start_time')
        stop_time = data.get('stop_time')

        if stop_time and start_time and stop_time < start_time:
            raise serializers.ValidationError("stop_time cannot be earlier than start_time.")
        return data

    def create(self, validated_data):
        appliance = validated_data['appliance']
        start_time = validated_data['start_time']
        stop_time = validated_data.get('stop_time')

        if stop_time:
            duration_hours = (stop_time - start_time).total_seconds() / 3600
            wattage = appliance.wattage
            energy = (wattage * duration_hours) / 1000
            validated_data['energy_consumed'] = round(energy, 3)  # rounded to 3 decimal places

        return super().create(validated_data)

    def update(self, instance, validated_data):
        appliance = validated_data.get('appliance', instance.appliance)
        start_time = validated_data.get('start_time', instance.start_time)
        stop_time = validated_data.get('stop_time', instance.stop_time)

        if stop_time:
            duration_hours = (stop_time - start_time).total_seconds() / 3600
            wattage = appliance.wattage
            energy = (wattage * duration_hours) / 1000
            validated_data['energy_consumed'] = round(energy, 3)

        return super().update(instance, validated_data)
    
class SlaveDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SlaveDevice
        fields = '__all__'

    def validate(self, data):
        controller = data.get('controller')
        room = data.get('room')

        # Support updates where controller isn't passed again
        if not controller:
            if self.instance:
                controller = self.instance.controller
            else:
                raise serializers.ValidationError("Controller is required.")

        homeowner = controller.homeowner  # Assumes Controller model has `homeowner = models.ForeignKey(...)`

        if room and room.homeowner != homeowner:
            raise serializers.ValidationError(
                "Selected room does not belong to the same homeowner as the controller."
            )

        return data

    def update(self, instance, validated_data):
        # Optional: Prevent changing `controller` or `mac_address` after creation
        validated_data.pop('controller', None)
        validated_data.pop('mac_address', None)
        return super().update(instance, validated_data)
