from django.urls import path

from apps.knowledge import api as views

urlpatterns = [
    path(
        'worlds/<slug:slug>/intel/claims/',
        views.intel_claim_list,
        name='intel-claim-list',
    ),
    path(
        'worlds/<slug:slug>/intel/claims/<uuid:claim_id>/',
        views.intel_claim_detail,
        name='intel-claim-detail',
    ),
    path(
        'worlds/<slug:slug>/intel/claims/<uuid:claim_id>/share/',
        views.intel_claim_share,
        name='intel-claim-share',
    ),
    path(
        'worlds/<slug:slug>/intel/claims/<uuid:claim_id>/verify/',
        views.intel_claim_verify,
        name='intel-claim-verify',
    ),
    path(
        'worlds/<slug:slug>/intel/evidence/<uuid:evidence_id>/',
        views.intel_evidence_detail,
        name='intel-evidence-detail',
    ),
]
