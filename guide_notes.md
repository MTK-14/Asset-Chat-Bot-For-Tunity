<!-- Notes the manuals don't state on any single slide.
     Separate each note with a line containing only three dashes.
     Write them the way a user would ASK.
     Re-run build_guide_index.py after editing this file. -->

---

Stock Take: you must create the Stock Take record on the WEB system first,
before anything can be scanned on the mobile app.

The correct order is:
1. On the web system, go to the Stock Taking module and create a new Stock
   Take record for the location you want to count.
2. On the mobile app, open Stock Taking. Select the correct Stock Take
   record, then scan the items.
3. The scanned data goes back to the web system.
4. On the web system, review and confirm the Stock Take result.

Stock Taking can be done in Online mode or Offline mode on the mobile app:
- Working ONLINE: the device needs a network connection, and the Stock Take
  record created on the web appears in the list.
- Working OFFLINE: download the data first while still on WiFi (for Stock
  Taking you need Item Category, Item Location and the Stock Taking List),
  then switch to Offline mode. After finishing, switch back to Online mode
  and upload the changes.

If the Stock Take record does not appear on the mobile app: check that it
was created on the web first, and -- if you are working offline -- that it
was created BEFORE you downloaded the data. A list created after the
download will not be on the device.

---

Picking List: the picking record must also be created on the WEB system
first. The mobile app can only pick against a record that already exists.

Order: create the Picking List on the web, then open it on the mobile app
to scan and pick the items, then the result goes back to the web.

Picking List works in Online mode and in Offline mode. If you will be
working offline, create the Picking List on the web BEFORE you download
data to the device -- a list created after the download will not be on the
device.

---

Web system vs mobile app -- which one do I use?

Many tasks can be done on EITHER the web system or the mobile app. Do not
assume a task is web-only or mobile-only unless it is listed below.

Modules available on the MOBILE app (from the mobile manual):
Registration, Update, Loan/Return, Relocation, Inspection, MRO,
Stock Taking, Picking List, Packing List, Check Status, Update with TagID,
Locating, Put In/Take Out, Container Stock Taking, Receiving, Check In/Out,
Container Relocation, Scrap, Split, Verification, Tag Filter, Association.

So adding a new item can be done on BOTH:
- On the web system, add the item in the Item Management module.
- On the mobile app, add the item using the Registration module.

In general the web system is better for bulk work, master data setup, user
management, analysis and reports; the mobile app is better when you are
physically with the items and scanning tags. But both can create and update
records -- it is a matter of which is more convenient, not a restriction.

---

Counting inventory -- two different things people mean:

If you want to physically count what is actually there (walk around and
scan items to compare against the system), that is the Stock Taking module.
Create the Stock Take record on the web, then scan on the mobile app.

If you just want to look up how many units of an item the system currently
shows, you do not need a Stock Take at all -- check the balance quantity of
the item in the Item Management module on the web system.

---

Tag ID (also called EPC internally): this is the number encoded on the
physical RFID or barcode tag that is attached to an item. It is the number
the scanner reads off the tag.

This is different from the other identifiers in the system:
- Tag ID is the physical tag's number.
- Asset No is the item's reference code.
- Display ID is another internal reference shown in some screens.

If an item has no Tag ID, it has not been tagged/registered with a physical
tag yet.

Note: the web system also has an Auto Tag Generation module, which can
auto-populate the Tag ID field when importing items from a CSV file.

---

Online mode and Offline mode on the mobile app -- and syncing.

The mobile app can be used in two modes, chosen when you sign in:

ONLINE mode -- the device works in real time against the web system, so the
device needs a network/WiFi connection. Anything you do appears on the web
system immediately.

OFFLINE mode -- for working where there is no network. Before setting off,
you must DOWNLOAD the data you need while still on WiFi. After finishing,
you switch back to Online mode and UPLOAD the changes.

The offline steps are: press "download" at the bottom right of the main
menu, tick the data types you need (when in doubt select ALL), press
Download, then switch to Offline and sign in with the SAME account that
downloaded the data. When you are done, exit, switch back to Online, sign
in, and press upload when prompted.

Important: any Stock Take List or Picking List created on the web AFTER you
downloaded will not be on the device. Create those lists first, then
download.

Not every module works offline. The modules available in Offline mode are:
Registration, Update, Loan/Return, Relocation, Inspection, MRO, Stock
Taking, Picking List, Check Status, Update with TagID, Locating, Check
In/Out, Scrap, Verification and IP Setting.

So if data is not appearing where you expect: if you are working online,
check the device's network connection. If you are working offline, check
that you downloaded the latest data before starting, and that you have
uploaded your changes after finishing.

---

How web and mobile modules relate -- three different patterns:

1. EITHER / OR -- the task can be done on web or on mobile, whichever is
   convenient. Adding an item is like this: Item Management on the web, or
   Registration on the mobile app. Both work; neither is required first.

2. WEB FIRST, THEN MOBILE -- the record must be created on the web system
   before the mobile app can act on it. Stock Taking and Picking List work
   this way: create the record on the web, scan against it on the mobile
   app, then the result syncs back to the web for review.

3. WEB ONLY -- administrative tasks that have no mobile equivalent, such as
   user management, master data setup, and reports.

When answering, say which pattern applies. Never tell the user a task is
impossible on one platform unless it is genuinely web-only.

---

Single vs Multiple -- what is the difference?

Single and Multiple is a property of the ITEM itself, not a feature of one
particular module. You choose it when the item is first created, and it
then affects how that item behaves everywhere in TCube.

- Single: the item is large enough to carry its own tag, so it gets one
  Tag ID of its own. Tracked as one individual unit.
- Multiple: the items are small or numerous and are not tagged one by one.
  They are grouped (for example in a box), and the box is tagged instead,
  with a quantity recorded against it.

Where you set it:
- On the WEB system: in the Item Management module, when you click Create
  to add a new item, you indicate Single or Multiple among the item
  parameters.
- On the MOBILE app: in the Registration module, you choose Single or
  Multiple when registering the tag.

Because it is an item property, it also affects many other modules on both
platforms -- for example Update, Relocation, Inspection, Check In/Out,
Receiving and Split all behave differently for Single versus Multiple
items. Some modules (such as Loan/Return and MRO on mobile) apply only to
Single type items.