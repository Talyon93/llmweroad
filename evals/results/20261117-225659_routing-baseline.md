# Eval run 20261117-225659_routing-baseline

- git: `3222b1a+dirty`, split: `dev`, cases: 62, errors: 0
- routing: `True`, chunking: `headings`, retrieval query: `both`
- models: {'cheap': 'claude-haiku-5-5', 'strong': 'claude-opus-5-5', 'judge': 'claude-opus-5-5', 'embedding': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'}
- agent cost: $0.5260, judge cost: $0.8843

| Metric | Value |
|---|---|
| Answer correctness | 71.0% |
| Intent accuracy | 100.0% |
| Behavior accuracy | 96.8% |
| Escalation precision | 85.7% |
| Escalation recall | 100.0% |
| Retrieval hit rate | 97.7% |
| Tool accuracy | 87.5% |
| Key facts present | 100.0% |
| Judge faithfulness (0-3) | 1.98 |
| Judge correctness (0-3) | 2.77 |
| Judge language & tone (0-3) | 2.77 |
| Latency p50 (s) | 3.91 |
| Latency p95 (s) | 11.26 |
| Cost per query (USD) | $0.0085 |

Calls by model: {'claude-haiku-5-5': 97, 'claude-opus-5-5': 40}  
Cost by node: {'classify': 0.0035, 'decide': 0.3453, 'escalate': 0.1773}

## Correctness by language

- de: 69% (n=13)
- en: 68% (n=28)
- fr: 100% (n=1)
- it: 75% (n=20)

## Failures

### pets-en-01
> Do you allow cats? Our cat travels with us everywhere.

- expected `['answer', 'escalate']` / intent `['pets']`; got `answered` / `pets` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 3, tone 3 - The core policy, that cats and other animals must be agreed in advance, is correctly conveyed without saying cats are simply allowed or forbidden. However, the reply invents a staff member (Giulia) and promises a direct follow-up that SOURCES do not support, and the guest could rely on that. The language and tone suit a family hotel email, and the reply asks for dates and party size.
- unsupported: ["I've noted your question, and Giulia will check with you directly about whether we can make an exception for your cat."]
- reply: Thank you for your message. Cats are not part of our standard policy: other animals such as cats or birds must be agreed with us in advance. I've noted your question, and Giulia will check with you directly about whether we can make an exception for your cat. In the meantime, if you tell us your dates and party size, we can also check availability for you.  Warm regards, CasaVaiano

### prices-de-01
> Gibt es einen Rabatt, wenn wir eine ganze Woche bleiben?

- expected `['answer']` / intent `['prices']`; got `escalated` / `prices` (reason: risk:discount_request)
- failed checks: behavior_ok
- judge: faithfulness 2, correctness 3, tone 3 - The draft accurately states the long-stay discount: 10% off accommodation for 7+ nights, excluding extras, the tourist tax and restaurant dinners. It also says Giulia will contact the guest personally, which no source supports and reads oddly because Giulia sends the reply herself. The summary is accurate, the German is polite and professional, and the draft sensibly asks for dates, group size and unit type.
- unsupported: ['Giulia wird sich persönlich bei Ihnen melden, um alles Weitere mit Ihnen zu besprechen.']
- reply: Vielen Dank für Ihre Nachricht! Giulia wird Ihnen so bald wie möglich persönlich antworten, in der Regel innerhalb von 24 Stunden.  CasaVaiano

### restaurant-en-01
> Is the restaurant open on Monday evening? We arrive on a Monday.

- expected `['answer']` / intent `['restaurant']`; got `answered` / `restaurant` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 3, tone 3 - The Monday closure, dinner hours and the Gambassi Terme and Certaldo recommendations all match SOURCES and fully meet EXPECTED. However, the reply assumes the guest is staying in an apartment, which the message does not say; a room guest could be misled into expecting a kitchen. The reply is in English, polite and suitable for email.
- unsupported: ['As an apartment guest, you are also welcome to cook in your own kitchen']
- reply: Thank you for your message. Unfortunately, the restaurant is closed on Mondays, as well as on Tuesdays and Wednesdays. Our dinner service runs from Thursday to Sunday, 19:30 to 22:00, and we do not serve lunch.  For your Monday arrival, we can recommend restaurants in Gambassi Terme (3 km away) and Certaldo (12 km away). As an apartment guest, you are also welcome to cook in your own kitchen, and if you would like, we can prepare a picnic basket for €18 per person, ordered the day before.  If you plan to dine with us on another evening during your stay, just let us know the dates and we will b

### restaurant-it-01
> Sono celiaca, potete garantire un menu senza glutine?

- expected `['answer', 'escalate']` / intent `['restaurant']`; got `answered` / `restaurant` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 3, tone 3 - The reply correctly states that gluten-free menus require 48 hours' notice, that traces cannot be guaranteed, and that coeliac guests should contact the agriturismo before booking to speak with Paolo; gluten-free bread at breakfast is also supported. However, it adds an offer to forward the request to 'Giulia', a person and service not mentioned in SOURCES, which the guest could act on. The language is polite, appropriate Italian and concise.
- unsupported: ['Se desidera, inoltro volentieri la sua richiesta a Giulia, che la ricontatterà.']
- reply: Gentile ospite,  grazie per averci scritto. Per gli ospiti celiaci il nostro menu senza glutine è possibile, ma va richiesto con almeno 48 ore di anticipo. Purtroppo la nostra cucina è piccola e lavora ogni giorno con farine, frutta a guscio e latticini, quindi non possiamo garantire l'assenza assoluta di tracce di glutine.  Le consigliamo pertanto di contattarci prima di prenotare, così che Paolo possa discutere personalmente il menu con lei e valutare insieme se possiamo offrirle la massima sicurezza. Se desidera, inoltro volentieri la sua richiesta a Giulia, che la ricontatterà.  Per la col

### restaurant-de-01
> Was kostet das Abendessen und muss man reservieren?

- expected `['answer']` / intent `['restaurant']`; got `answered` / `restaurant` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 3, tone 3 - All prices, the menu details, the reservation deadline and the opening hours match SOURCES. However, SOURCES never mention Giulia or a request-forwarding service, so this is an unsupported offer the guest could act on. The reply answers both questions fully in polite German; it adds some extra detail but stays reasonably concise.
- unsupported: ['Wenn Sie möchten, leite ich Ihre Reservierungsanfrage an Giulia weiter.']
- reply: Guten Tag,  das Abendessen im CasaVaiano ist ein viergängiges toskanisches Menü zum Preis von €38 pro Person, Getränke sind nicht inbegriffen. Kinder unter 10 Jahren zahlen €20. Das Menü wechselt jede Woche und nutzt Gemüse aus unserem Garten, unser eigenes Olivenöl und Fleisch von lokalen Höfen. Unser eigener Rotwein kostet €22 pro Flasche, ein Glas Hauswein €5.  Ja, eine Reservierung ist erforderlich, auch für Gäste, die bei uns übernachten. Bitte reservieren Sie bis 12:00 Uhr am selben Tag. Das Restaurant serviert Abendessen von Donnerstag bis Sonntag, jeweils von 19:30 bis 22:00 Uhr; monta

### restaurant-it-02
> Possiamo venire a cena da voi anche se non dormiamo lì? Saremmo in 4, sabato prossimo.

- expected `['answer']` / intent `['restaurant']`; got `answered` / `restaurant` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 3, tone 1 - The reply covers everything EXPECTED asks for: non-guests are welcome subject to availability, Saturday is a dinner day, the menu is €38 and booking is required. However, it invents a booking process involving 'Giulia', who does not appear in SOURCES, and calls the set menu a 'degustazione'. It also opens with leaked English reasoning before the Italian reply, which is unsuitable for an email to the guest.
- unsupported: ['organizzo la richiesta e la inoltro a Giulia, che conferma la prenotazione', 'menù degustazione']
- reply: Today is Tuesday 2026-11-17, so "sabato prossimo" is Saturday 2026-11-21 or 2026-11-28 depending on how you count. The restaurant serves dinner Thursday to Sunday, so Saturday works. Non-guests are welcome subject to availability, and the reservation must be made by 12:00 on the same day.  Rispondo in italiano:  Buongiorno, grazie per averci scritto! Sì, siamo aperti anche a chi non alloggia da noi, compatibilmente con la disponibilità. Il nostro ristorante serve la cena da giovedì a domenica, dalle 19:30 alle 22:00, con un menù degustazione toscano di quattro portate a €38 a persona, bevande 

### restaurant-de-02
> Gibt es vegane Optionen beim Frühstück und beim Abendessen?

- expected `['answer']` / intent `['restaurant']`; got `answered` / `restaurant` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 2, tone 2 - Excluding only cheese and cured meats implies the yogurt, homemade cakes and other buffet items are vegan, which SOURCES do not state; a vegan guest could act on this, though the listed items themselves are supported. The reply correctly conveys plant-based milk, fruit and the 48-hour vegan dinner request, but the misleading breakfast framing weakens the main answer. The German is polite, but the reply is padded with unrequested coeliac, allergy and schedule details.
- unsupported: ['dazu Obst, Joghurt, Brot, Marmelade und Kuchen. Eier gibt es auf Wunsch, und der Käse sowie die Wurst sind natürlich nicht vegan.']
- reply: Guten Tag,  Zum Frühstück gibt es immer glutenfreies Brot und pflanzliche Milch, dazu Obst, Joghurt, Brot, Marmelade und Kuchen. Eier gibt es auf Wunsch, und der Käse sowie die Wurst sind natürlich nicht vegan.  Beim Abendessen servieren wir ein viergängiges toskanisches Menü (€38 pro Person, Getränke nicht inbegriffen), das sich jede Woche ändert und mit Gemüse aus unserem Garten zubereitet wird. Ein veganes Menü ist auf Anfrage möglich, wenn Sie es uns mindestens 48 Stunden vorher mitteilen. Eine vegetarische Alternative haben wir immer. Bitte beachten Sie, dass unsere Küche klein ist und tä

### checkin-en-02
> Is a late check-out possible on our last day?

- expected `['answer']` / intent `['checkin']`; got `answered` / `checkin` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 3, tone 3 - The core facts are supported: late check-out until 13:00 on request for €25, depending on next arrivals, with standard check-out by 10:30. However, the SOURCES name Giulia only for refunds and cancellation exceptions, so routing late check-out requests to her is an invented process the guest could rely on. The reply fully matches EXPECTED, is polite and in English, and asks for the check-out date.
- unsupported: ["we can't guarantee it until we check with the team", 'I can also check availability for you', "I'll pass your request to Giulia to confirm the late check-out"]
- reply: Yes, a late check-out until 13:00 may be possible on request for €25. It depends on the next arrivals, so we can't guarantee it until we check with the team. Standard check-out is by 10:30.  If you let me know your dates, I can also check availability for you. Just tell me the check-out date and I'll pass your request to Giulia to confirm the late check-out.  CasaVaiano

### services-en-01
> Can you pick us up from Florence airport?

- expected `['answer']` / intent `['services', 'directions']`; got `answered` / `services` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 3, tone 3 - The reply correctly says there is no shuttle and offers a taxi at about €110, paid to the driver, with polite optional car-rental advice. However, SOURCES give no drive time from Florence airport (only 55 minutes from Florence) and mention Giulia only for refunds and exceptions, not taxi bookings. These are claims the guest could act on.
- unsupported: ['roughly a one-hour drive', 'we can arrange the taxi with Giulia']
- reply: We don't run a shuttle service ourselves, but we can book a local taxi for you from Florence airport. The indicative price is about €110, and it is paid directly to the driver. Florence airport is about 60 km from us, roughly a one-hour drive.  If you'd like, send us your arrival date and time and the number of passengers, and we can arrange the taxi with Giulia. Alternatively, if you prefer to drive yourself, a car is strongly recommended in the area, and car rental is available at the airport.  Warm regards, CasaVaiano

### policies-it-02
> I bambini possono stare in piscina da soli?

- expected `['answer']` / intent `['policies', 'services']`; got `escalated` / `services` (reason: risk:legal_or_safety)
- failed checks: behavior_ok
- judge: faithfulness 2, correctness 3, tone 3 - The draft accurately states the under-12 supervision rule, the absence of a lifeguard and the pool's season and hours, all supported by SOURCES. However, it promises a personal follow-up from Giulia that is not in SOURCES, which is also awkward because Giulia is the one sending the reply. The summary correctly identifies the request, the policy and the current seasonal closure, and the reply is polite, professional Italian.
- unsupported: ['Giulia la contatterà personalmente per qualsiasi ulteriore chiarimento.']
- reply: Grazie per il messaggio! Giulia le risponderà personalmente al più presto, di solito entro 24 ore.  CasaVaiano

### booking-it-01
> Buongiorno, siamo in due e vorremmo venire dal 10 al 17 luglio 2027. Avete una camera libera? Quanto costa?

- expected `['answer']` / intent `['booking']`; got `answered` / `booking` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 2, tone 3 - Prices, discount, tourist tax, deposit amounts and check-in times match the sources, but the reply invents a named staff member (Giulia) and a confirmation process. It also states a 30% deposit policy that is only inferred from the tool figures, not stated in SOURCES. The main question is answered correctly in polite Italian, though the available Granaio apartment is omitted.
- unsupported: ['Per confermare la prenotazione serve un acconto del 30%', "La conferma la dà Giulia quando riceve l'acconto.", 'le giriamo subito la richiesta e lei vi ricontatterà con tutti i dettagli']
- reply: Buongiorno,  grazie per averci scritto! Per due persone dal 10 al 17 luglio 2027 (7 notti, alta stagione) abbiamo ancora queste camere libere:  - Ulivo, camera doppia: €980, con lo sconto del 10% per i soggiorni di almeno 7 notti si scende a €882 - Cipresso, camera doppia o con due letti singoli: €980, con lo sconto si scende a €882 - Torre, junior suite: €1.610, con lo sconto si scende a €1.449  In tutte le camere la colazione per entrambi è inclusa. La tassa di soggiorno è di €21 e si paga sul posto. Il check-in è dalle 15:00 alle 20:00 e il check-out entro le 10:30.  Per confermare la preno

### booking-en-02
> Do you have anything for 4 people (2 adults, kids aged 6 and 9) from 2 to 9 October 2027? A place with a kitchen would be ideal.

- expected `['answer']` / intent `['booking']`; got `answered` / `booking` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 2, tone 3 - Prices, discount, deposit amount, tourist tax and the Granaio description all match the SOURCES. However, the booking procedure (Giulia confirming after a 30% deposit) is not in the SOURCES, and the claim that Vigna has no kitchen is only implied. The reply also never mentions that Fienile is booked, a minor point from EXPECTED.
- unsupported: ["I can't confirm the booking myself.", 'Giulia confirms each reservation once the 30% deposit is paid', 'It has no kitchen.']
- reply: Dear guest,  Thank you for getting in touch. We have a good option for your family from 2 to 9 October 2027 (7 nights).  Since you'd like a kitchen, the best fit is Granaio, our old granary. It's an 80 m² apartment on two floors with two double bedrooms (one can be made up as a twin), two bathrooms and a sofa bed for two in the living room. It has a full kitchen with an oven and dishwasher, a washing machine, and an outdoor dining area with a barbecue. The bedrooms have air conditioning, and the living area has ceiling fans. For 2 adults and children aged 6 and 9, the price is €1,540 at €220 p

### booking-en-03
> Is the Granaio apartment free from 1 to 3 July 2027?

- expected `['answer']` / intent `['booking']`; got `answered` / `booking` (reason: None)
- failed checks: escalated, tools_ok
- judge: faithfulness 0, correctness 0, tone 3 - The reply invents a 30% deposit policy and a staff member named Giulia, neither of which appears in SOURCES. It never says that Granaio is booked on those dates or mentions the 7-night minimum stay in high season, and it asks for unnecessary details instead of answering. The language is polite, professional and in English.
- unsupported: ['Giulia confirms reservations once the 30% deposit is paid', "I'll let you know right away whether the Granaio is free and what it would cost", "I can send her your request whenever you're ready"]
- reply: Thank you for your interest in the Granaio. It's our old granary, 80 m² on two floors, with two double bedrooms, a sofa bed for two, two bathrooms and a full kitchen. It sleeps up to 6.  Before I check 1 to 3 July 2027 (2 nights) and get you an exact price, could you tell me:  1. How many adults will be staying? 2. Are any children coming, and how old are they? 3. Will you be bringing a dog?  Once I have that, I'll let you know right away whether the Granaio is free and what it would cost. Giulia confirms reservations once the 30% deposit is paid, and I can send her your request whenever you'r

### booking-it-04
> Vorremmo prenotare la camera Vigna per 5 persone (3 adulti e 2 ragazzi di 12 e 15 anni) dal 3 al 6 settembre 2027.

- expected `['answer']` / intent `['booking']`; got `answered` / `booking` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 3, tone 3 - Availability, extra bed and the quote breakdown (€630 + €90 = €720, €189 deposit, €18 tourist tax) match the tool results, so EXPECTED is fully met. However, the booking process (Giulia confirming, the 30% deposit framing, forwarding the request) is not in SOURCES, and the tool's 7-night minimum for these dates is generalised to all of September; the guest could act on these claims. The Italian is polite and professional, and the reply asks for a name and contact.
- unsupported: ['Non posso confermare io la prenotazione.', "Sarà Giulia a confermarla dopo che avrà ricevuto l'acconto del 30%.", 'Se volete, posso inoltrarle subito la vostra richiesta.', 'a settembre il Granaio si prenota solo per almeno 7 notti']
- reply: Gentili ospiti,  grazie per averci scritto. Abbiamo controllato: la camera Vigna è libera dal 3 al 6 settembre 2027 (3 notti) e può ospitare 5 persone aggiungendo un letto extra.  Ecco il preventivo per 3 adulti e 2 ragazzi di 12 e 15 anni. Le 3 notti in alta stagione costano €210 a notte, quindi €630, colazione inclusa. Il letto extra costa €90, per un totale di €720. Per confermare serve un acconto di €189. La tassa di soggiorno di €18 si paga in struttura.  La Vigna è di 28 m², con un letto matrimoniale e due letti singoli in un'alcova separata. In cinque si sta piuttosto stretti. Di solito

### booking-en-06
> Can we book the Cipresso room for 3 nights in mid-May 2027? We'll have our small dog with us.

- expected `['answer', 'clarify']` / intent `['booking', 'pets']`; got `answered` / `booking` (reason: None)
- failed checks: escalated
- judge: faithfulness 0, correctness 3, tone 2 - The reply correctly says dogs aren't allowed in Cipresso, suggests Ulivo and Fienile with accurate details, and asks for exact dates. However, it invents a booking policy (Giulia confirming reservations after a 30% deposit) that SOURCES do not support. The English is polite, but the reply is somewhat long and uses markdown bold, which suits an email less well.
- unsupported: ["When you're ready to book, I can pass your request to Giulia.", 'She confirms reservations once the 30% deposit has been paid.', 'which is lovely with a dog']
- reply: Hello, and thank you for thinking of CasaVaiano for your May stay!  Unfortunately, dogs can't stay in the Cipresso room. Dogs are allowed only in our Ulivo room and our Fienile apartment, with one dog per unit at €15 per night. (Assistance dogs are welcome in every unit free of charge, so please let us know if yours is one.)  Here are two options for you and your dog:  1. **Ulivo**: a double room on the ground floor of the farmhouse, 18 m², with a garden view. It has one double bed and sleeps up to 2 guests. You can reach it from the parking area without any steps. 2. **Fienile**: our former h

### booking-de-04
> Wir sind 2 Erwachsene und ein Baby (8 Monate). Ist das Zimmer Ulivo vom 1. bis 4. April 2027 frei?

- expected `['answer']` / intent `['booking']`; got `answered` / `booking` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 3, tone 2 - The reply correctly confirms availability, the free cot, and €345 with breakfast, and the tourist tax, high chairs, and check-in times are all supported. However, it invents a booking process: a staff member named Giulia who confirms bookings is not in SOURCES, and the guest could act on this. It is in German and polite but longer than needed (an unrequested room description), and the closing line about remembering whether they need the cot is awkward.
- unsupported: ['Ich kann das Zimmer leider nicht selbst für Sie buchen.', 'Wenn Sie möchten, leite ich Ihre Anfrage gern an Giulia weiter.', 'Sie bestätigt die Buchung, sobald die Anzahlung von 30 % (€103,50) eingegangen ist.', 'Mit Kinderwagen ist das sehr praktisch.']
- reply: Liebe Gäste,  vielen Dank für Ihre Anfrage! Das Zimmer Ulivo ist vom 1. bis 4. April 2027 (3 Nächte) für Sie beide frei. Ein Babybett für Ihr Kleines stellen wir Ihnen auf Wunsch kostenlos ins Zimmer.  Der Aufenthalt kostet insgesamt €345 (3 Nächte zu je €115), das Frühstück ist inklusive. Hinzu kommt die Kurtaxe von €9, die Sie vor Ort bezahlen. Im Restaurant gibt es auch Hochstühle.  Ulivo ist ein 18 m² großes Doppelzimmer im Erdgeschoss unseres Bauernhauses. Es hat Blick in den Garten und ein Doppelbett (160x200 cm). Vom Parkplatz aus erreichen Sie das Zimmer ohne Stufen, und das Bad hat ei

### other-en-01
> Can you recommend a good restaurant in Florence for our anniversary dinner?

- expected `['answer', 'escalate']` / intent `['other', 'restaurant', 'services']`; got `answered` / `other` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 3, tone 3 - The reply correctly avoids inventing Florence restaurants and accurately describes the in-house dinner (days, hours, price, reservation deadline), which satisfies EXPECTED. However, it names a contact person, 'Giulia', who does not appear in SOURCES, and the guest could act on this. The availability-check offer is also not backed by SOURCES.
- unsupported: ['Giulia can help with that', "just send me your dates and the number of guests and I'll check availability"]
- reply: I'm sorry, but I can't recommend restaurants in Florence, as that's outside what I can speak to with confidence. For your anniversary, you're very welcome to dine with us: our restaurant serves a four-course Tuscan set menu at €38 per person (drinks excluded), Thursday to Sunday from 19:30 to 22:00, and reservations are required by 12:00 on the same day. Children under 10 pay €20. We also host anniversary celebrations, so if you'd like something more special, Giulia can help with that.  If you'd like to stay with us as well, just send me your dates and the number of guests and I'll check avail

### spam-en-01
> Buy cheap luxury watches now at www.example-watches.test !!! Best prices guaranteed

- expected `['escalate', 'answer']` / intent `['other']`; got `answered` / `other` (reason: None)
- failed checks: escalated
- judge: faithfulness 1, correctness 1, tone 3 - The message is spam, but the reply engages with it, pitches the property and asks the sender for dates and guest numbers instead of declining minimally. It also states a location (near Gambassi Terme) and a promotions policy that SOURCES do not support. The English is polite and professional.
- unsupported: ["we don't take part in outside promotions or links", 'in the Tuscan countryside near Gambassi Terme']
- reply: Thank you for your message. Unfortunately, CasaVaiano can't help with watch purchases, and we don't take part in outside promotions or links.  If you're interested in staying with us in the Tuscan countryside near Gambassi Terme, we'd be happy to help with availability, prices, or information about our apartments, extras, or events. Just let us know your dates and number of guests.  Warm regards, CasaVaiano

