"""Shared model factories for tests."""

from __future__ import annotations

from leadforge import models


def make_job(**kwargs) -> models.ResearchJob:
    defaults = {
        "industry": "Jewelry Stores",
        "country": "United States",
        "region": "California",
        "requested_leads": 100,
    }
    defaults.update(kwargs)
    return models.ResearchJob(**defaults)


def make_company(**kwargs) -> models.Company:
    defaults = {
        "company_name": "ABC Jewelry LLC",
        "normalized_name": "abc jewelry",
        "website": "https://www.abcjewelry.example.com/",
        "normalized_domain": "abcjewelry.example.com",
        "industry": "Jewelry Stores",
        "country": "United States",
        "region": "California",
        "city": "Los Angeles",
        "public_email": "info@abcjewelry.example.com",
        "source_url": "https://www.abcjewelry.example.com/",
        "is_synthetic": True,
    }
    defaults.update(kwargs)
    return models.Company(**defaults)


def make_result(job: models.ResearchJob, company: models.Company, **kwargs) -> models.LeadResearchResult:
    defaults = {
        "quality_score": 85,
        "score_factors": {"website": 20, "company_name": 20, "location": 15,
                          "phone": 15, "public_email": 20, "source": 10},
        "validation_status": "valid",
        "validation_issues": [],
        "verification_status": "unverified",
    }
    defaults.update(kwargs)
    return models.LeadResearchResult(job=job, company=company, **defaults)
