# Phase 4: Coach Bridge + Game Scraper

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make coach conversations update the daily plan (mutation preview → apply), and auto-detect game appearances to feed the weekly model.

**Architecture:** The chat endpoint gains a `mutations` field in responses when the LLM suggests plan changes. Coach.jsx renders these as diff cards with Apply/Keep buttons. A game appearance detector runs after each game day, scrapes box score data from the schedule, and updates pitcher_training_model for relievers who appeared.

**Tech Stack:** Python/FastAPI, React, Supabase, existing scrape_schedule.py infrastructure

---

## Tasks

### Task 1: Add plan_mutation detection to chat endpoint
### Task 2: Add /apply-mutations endpoint  
### Task 3: Update QA prompt with mutation instructions
### Task 4: Add MutationPreview component
### Task 5: Wire mutations into Coach.jsx
### Task 6: Game appearance detector
### Task 7: Update CLAUDE.md
