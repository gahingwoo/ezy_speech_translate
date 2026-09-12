# Trademark policy

EzySpeech is free software under the GNU Affero General Public License,
version 3. That licence grants rights in the copyright of the code. It does
not grant rights in the names and marks that identify the project, and
section 7(e) of the licence expressly allows those to be withheld. This
document says what is withheld and, more importantly, what is not.

## The marks

- **EzySpeech** and **EzySpeechTranslate**, as names of this software.
- The **Engineered by gahingwoo** wordmark and the mark drawn beside it.

## What you may do without asking

- Run the software, modified or not, for any purpose, including commercially.
- Say truthfully that your deployment runs EzySpeech, is built on EzySpeech,
  or is powered by EzySpeech.
- Use the name in documentation, articles, talks, reviews and comparisons to
  refer to this project.
- Fork the code and say that your fork is derived from EzySpeech.

None of this needs permission. Calling a thing by its name is not
infringement, and this policy does not pretend otherwise.

## What needs permission

- Naming your modified version or your hosted service EzySpeech, or a name
  close enough to be taken for it.
- Using the marks in a way that suggests this project endorses, supports, or
  is answerable for your deployment.
- Using the marks in a domain name, an application name, a company name or a
  product name.

The reason is narrow. Someone who meets a broken, abandoned or hostile
deployment called EzySpeech has no way to tell it from this one, and the
judgement lands on the person who wrote it. Withholding the name is the only
way to keep those two things separable.

## Running it under your own name is supported

You do not need to patch anything. The software ships with the configuration
to rebrand itself, and that is the intended route:

```yaml
branding:
  app_name: Your Name Here
  user_title: Your Name Here Listener
  admin_title: Your Name Here Admin
  login_title: Your Name Here Admin
assets:
  brand_icon: "🎙️"
  favicon: ""
  login_icon: "🎙️"
```

`app/oem_manager.py` holds the full set of keys and their defaults.

## The credit stays

Section 7(b) of the licence permits requiring that author attributions be
preserved. This project requires it: the **Engineered by gahingwoo** credit
in the about dialog must remain in every deployment, rebranded or not.

It names who wrote the software. It does not claim who runs it, and it does
not stop you putting your own name on everything else.

## Asking

Write to gahing@gahingwoo.com. Permission for anything outside this policy
is given in writing or not at all.
