from django import forms


class BarcodeForm(forms.Form):
    youtube_link = forms.CharField(label='Enter video path', max_length=100, required=True)
