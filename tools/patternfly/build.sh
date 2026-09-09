#!/bin/sh
# Assemble app/static/patternfly/patternfly.css from the parts of
# @patternfly/patternfly this app uses, so the pages do not ship the 1.8 MB
# full bundle. Needs node and npm; nothing else does. Run from the repo root:
#
#   sh tools/patternfly/build.sh
#
# The output is committed, so a normal checkout needs no build step.
#
# The component list grows as pages are converted. Add what a page needs, run
# this, and commit the result.
set -e

COMPONENTS="Login/login Form/form FormControl/form-control \
            AboutModalBox/about-modal-box \
            Button/button Title/title Content/content \
            Card/card HelperText/helper-text \
            BackgroundImage/background-image Brand/brand List/list \
            Page/page Masthead/masthead Nav/nav Backdrop/backdrop \
            EmptyState/empty-state Label/label Badge/badge Slider/slider \
            ModalBox/modal-box Alert/alert Alert/alert-group \
            TextInputGroup/text-input-group Switch/switch Divider/divider \
            Icon/icon SkipToContent/skip-to-content \
            DescriptionList/description-list Table/table Table/table-grid Check/check \
            Panel/panel Spinner/spinner DragDrop/drag-drop \
            InputGroup/input-group ProgressStepper/progress-stepper \
            DataList/data-list Tabs/tabs TabContent/tab-content Wizard/wizard \
            NumberInput/number-input Toolbar/toolbar \
            Drawer/drawer JumpLinks/jump-links Menu/menu \
            ActionList/action-list Popover/popover"
LAYOUTS="Bullseye/bullseye Stack/stack Flex/flex Grid/grid Split/split Level/level \
         Gallery/gallery"

OUT=app/static/patternfly
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

( cd "$WORK" && npm pack @patternfly/patternfly@6 >/dev/null 2>&1 && tar xzf patternfly-patternfly-*.tgz )
PKG="$WORK/package"
mkdir -p "$OUT"

{
  echo "/* Built by tools/patternfly/build.sh from @patternfly/patternfly $(node -p "require('$PKG/package.json').version"). Do not edit. */"
  cat "$PKG/patternfly-base.css"
  for c in $COMPONENTS; do cat "$PKG/components/$c.css"; done
  for l in $LAYOUTS; do cat "$PKG/layouts/$l.css"; done
} > "$OUT/patternfly.css"

# PatternFly's own @font-face rules resolve relative to the stylesheet, so the
# fonts go where it looks for them rather than somewhere of our choosing. The
# pages currently pull Red Hat from Google Fonts; serving them here means one
# less third party and no request leaving the network the app runs on.
for d in RedHatDisplay RedHatText RedHatMono; do
  mkdir -p "$OUT/assets/fonts/$d"
  cp "$PKG/assets/fonts/$d/"*VF.woff2 "$PKG/assets/fonts/$d/"*VF-Italic.woff2 "$OUT/assets/fonts/$d/"
done

# The background pattern PatternFly's login and about pages are designed around.
mkdir -p "$OUT/assets/images"
cp "$PKG/assets/images/pf-background.svg" "$OUT/assets/images/"

node -p "'@patternfly/patternfly ' + require('$PKG/package.json').version" > "$OUT/VERSION"
echo "components: $COMPONENTS" >> "$OUT/VERSION"
echo "layouts: $LAYOUTS" >> "$OUT/VERSION"

wc -c "$OUT/patternfly.css"
