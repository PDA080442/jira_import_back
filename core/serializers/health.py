from rest_framework import serializers


class CheckResultSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "error"])
    detail = serializers.CharField()


class HealthLiveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok"])


class HealthReadySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "error"])
    checks = serializers.DictField(child=CheckResultSerializer())
