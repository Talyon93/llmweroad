# Eval run 20261117-230359_routing-baseline-v2judge

- git: `3222b1a+dirty`, split: `dev`, cases: 62, errors: 0
- routing: `True`, chunking: `headings`, retrieval query: `both`
- models: {'cheap': 'claude-haiku-5-5', 'strong': 'claude-opus-5-5', 'judge': 'claude-opus-5-5', 'embedding': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'}
- agent cost: $0.5260, judge cost: $0.9761

| Metric | Value |
|---|---|
| Answer correctness | 88.7% |
| Intent accuracy | 100.0% |
| Behavior accuracy | 96.8% |
| Escalation precision | 85.7% |
| Escalation recall | 100.0% |
| Retrieval hit rate | 97.7% |
| Tool accuracy | 87.5% |
| Key facts present | 100.0% |
| Judge faithfulness (0-3) | 2.50 |
| Judge correctness (0-3) | 2.85 |
| Judge language & tone (0-3) | 2.71 |
| Latency p50 (s) | 3.91 |
| Latency p95 (s) | 11.26 |
| Cost per query (USD) | $0.0085 |

Calls by model: {'claude-haiku-5-5': 97, 'claude-opus-5-5': 40}  
Cost by node: {'classify': 0.0035, 'decide': 0.3453, 'escalate': 0.1773}

## Correctness by language

- de: 85% (n=13)
- en: 89% (n=28)
- fr: 100% (n=1)
- it: 90% (n=20)

## Failures

### prices-de-01
> Gibt es einen Rabatt, wenn wir eine ganze Woche bleiben?

- expected `['answer']` / intent `['prices']`; got `escalated` / `prices` (reason: risk:discount_request)
- failed checks: behavior_ok
- judge: faithfulness 3, correctness 3, tone 3 - The draft accurately states the long-stay discount policy from SOURCES (10% on accommodation for 7+ nights, excluding extras, tourist tax and restaurant dinners), which matches the expected answer and invents nothing. The summary correctly identifies the request and notes the missing dates, unit and group size. The reply is in polite, professional German, asks for the needed details and is signed correctly.
- reply: Vielen Dank für Ihre Nachricht! Giulia wird Ihnen so bald wie möglich persönlich antworten, in der Regel innerhalb von 24 Stunden.  CasaVaiano

### restaurant-en-01
> Is the restaurant open on Monday evening? We arrive on a Monday.

- expected `['answer']` / intent `['restaurant']`; got `answered` / `restaurant` (reason: None)
- judge: faithfulness 1, correctness 3, tone 3 - The reply correctly states that the restaurant is closed on Mondays, gives the Thursday–Sunday 19:30–22:00 dinner hours and recommends restaurants in Gambassi Terme and Certaldo, matching EXPECTED. However, it assumes without any basis that the guest is staying in an apartment and therefore has a kitchen, which a room guest could act on. The tone and language are appropriate and concise, and the reply invites the guest to share their dates for dinner on other evenings.
- unsupported: ['As an apartment guest, you are also welcome to cook in your own kitchen']
- reply: Thank you for your message. Unfortunately, the restaurant is closed on Mondays, as well as on Tuesdays and Wednesdays. Our dinner service runs from Thursday to Sunday, 19:30 to 22:00, and we do not serve lunch.  For your Monday arrival, we can recommend restaurants in Gambassi Terme (3 km away) and Certaldo (12 km away). As an apartment guest, you are also welcome to cook in your own kitchen, and if you would like, we can prepare a picnic basket for €18 per person, ordered the day before.  If you plan to dine with us on another evening during your stay, just let us know the dates and we will b

### restaurant-it-02
> Possiamo venire a cena da voi anche se non dormiamo lì? Saremmo in 4, sabato prossimo.

- expected `['answer']` / intent `['restaurant']`; got `answered` / `restaurant` (reason: None)
- judge: faithfulness 2, correctness 3, tone 1 - The reply correctly covers every expected point: non-guests are welcome subject to availability, Saturday is a dinner day, the set menu is €38 and a reservation is required by 12:00 on the day; it also asks the guest to confirm the date and give details. It adds minor unsupported advice to write as soon as possible and calls the set menu a 'degustazione', which the sources do not say. The reply opens with leaked English internal reasoning and the line 'Rispondo in italiano:', which is a noticeable language and professionalism problem for a guest email.
- unsupported: ['Vi consiglio però di scriverci al più presto, così possiamo verificare i posti.', 'menù degustazione']
- reply: Today is Tuesday 2026-11-17, so "sabato prossimo" is Saturday 2026-11-21 or 2026-11-28 depending on how you count. The restaurant serves dinner Thursday to Sunday, so Saturday works. Non-guests are welcome subject to availability, and the reservation must be made by 12:00 on the same day.  Rispondo in italiano:  Buongiorno, grazie per averci scritto! Sì, siamo aperti anche a chi non alloggia da noi, compatibilmente con la disponibilità. Il nostro ristorante serve la cena da giovedì a domenica, dalle 19:30 alle 22:00, con un menù degustazione toscano di quattro portate a €38 a persona, bevande 

### restaurant-de-02
> Gibt es vegane Optionen beim Frühstück und beim Abendessen?

- expected `['answer']` / intent `['restaurant']`; got `answered` / `restaurant` (reason: None)
- judge: faithfulness 1, correctness 2, tone 2 - The reply correctly conveys plant-based milk and fruit at breakfast and vegan dinner menus with 48 hours' notice. However, by listing yogurt and homemade cakes right after the vegan items, it implies they are vegan, which SOURCES do not support and a guest could act on. The German is polite and appropriate but padded with unrequested details (price, allergy notice, opening hours).
- unsupported: ['dazu Obst, Joghurt, Brot, Marmelade und Kuchen (implied as vegan breakfast options; SOURCES do not say yogurt, cakes or bread are vegan)']
- reply: Guten Tag,  Zum Frühstück gibt es immer glutenfreies Brot und pflanzliche Milch, dazu Obst, Joghurt, Brot, Marmelade und Kuchen. Eier gibt es auf Wunsch, und der Käse sowie die Wurst sind natürlich nicht vegan.  Beim Abendessen servieren wir ein viergängiges toskanisches Menü (€38 pro Person, Getränke nicht inbegriffen), das sich jede Woche ändert und mit Gemüse aus unserem Garten zubereitet wird. Ein veganes Menü ist auf Anfrage möglich, wenn Sie es uns mindestens 48 Stunden vorher mitteilen. Eine vegetarische Alternative haben wir immer. Bitte beachten Sie, dass unsere Küche klein ist und tä

### services-en-01
> Can you pick us up from Florence airport?

- expected `['answer']` / intent `['services', 'directions']`; got `answered` / `services` (reason: None)
- judge: faithfulness 1, correctness 3, tone 3 - The reply correctly states there is no shuttle, that a taxi from Florence airport costs about €110 and is paid to the driver, and adds the supported facts about car rental and the 60 km distance. However, the one-hour drive time from the airport is not in SOURCES (only Florence city at 55 minutes is given), and involving Giulia in the taxi booking is not stated. The tone, language and sign-off are appropriate.
- unsupported: ['roughly a one-hour drive', 'we can arrange the taxi with Giulia']
- reply: We don't run a shuttle service ourselves, but we can book a local taxi for you from Florence airport. The indicative price is about €110, and it is paid directly to the driver. Florence airport is about 60 km from us, roughly a one-hour drive.  If you'd like, send us your arrival date and time and the number of passengers, and we can arrange the taxi with Giulia. Alternatively, if you prefer to drive yourself, a car is strongly recommended in the area, and car rental is available at the airport.  Warm regards, CasaVaiano

### policies-it-02
> I bambini possono stare in piscina da soli?

- expected `['answer']` / intent `['policies', 'services']`; got `escalated` / `services` (reason: risk:legal_or_safety)
- failed checks: behavior_ok
- judge: faithfulness 3, correctness 3, tone 3 - The draft accurately states the under-12 accompaniment rule, the lack of a lifeguard and the pool hours, all as given in SOURCES, and promises nothing beyond a personal follow-up from Giulia. The summary correctly identifies the request, the safety reason for escalation and that the pool is currently closed for the season. The reply is in polite, professional Italian and signed as instructed.
- reply: Grazie per il messaggio! Giulia le risponderà personalmente al più presto, di solito entro 24 ore.  CasaVaiano

### booking-en-03
> Is the Granaio apartment free from 1 to 3 July 2027?

- expected `['answer']` / intent `['booking']`; got `answered` / `booking` (reason: None)
- failed checks: tools_ok
- judge: faithfulness 3, correctness 1, tone 2 - The Granaio description and the deposit/Giulia statement are supported by the sources and operator instructions. The reply never answers the availability question: it does not say Granaio is booked or mention the 7-night high-season minimum, and instead asks for guest details that an availability check does not need. The tone is warm and in English, but the numbered list breaks the no-lists style rule.
- reply: Thank you for your interest in the Granaio. It's our old granary, 80 m² on two floors, with two double bedrooms, a sofa bed for two, two bathrooms and a full kitchen. It sleeps up to 6.  Before I check 1 to 3 July 2027 (2 nights) and get you an exact price, could you tell me:  1. How many adults will be staying? 2. Are any children coming, and how old are they? 3. Will you be bringing a dog?  Once I have that, I'll let you know right away whether the Granaio is free and what it would cost. Giulia confirms reservations once the 30% deposit is paid, and I can send her your request whenever you'r

