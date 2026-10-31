/**
 * Built-in Scenarios for Customer Simulator Agent
 */

const DEFAULT_SCENARIOS = [
  {
    id: 'damaged_delivery',
    title: 'Damaged Luxury Delivery',
    domain: 'E-Commerce & Retail',
    difficulty: 'Medium',
    description: 'Espresso machine arrived shattered in pieces before an important anniversary dinner.',
    initialCustomerMessage: 'Hello, I just opened package #ORD-98214 and the ceramic espresso maker is completely smashed into pieces. This was supposed to be our anniversary gift for tonight! I need this resolved right now.',
    context: {
      orderId: 'ORD-98214',
      productName: 'Artisan Ceramic Espresso Set',
      amount: '$149.99',
      orderDate: '3 days ago',
      deliveryDate: 'Today, 2 hours ago',
      photosAvailable: true,
      hasOriginalPackaging: true,
      urgencyReason: 'Anniversary celebration tonight at 7 PM'
    },
    goals: {
      primary: 'Full refund back to original payment card ($149.99) OR same-day replacement',
      acceptableAlternatives: ['Overnight express replacement sent with no return hassle', 'Instant store credit of $180 (with bonus)'],
      unacceptableOffers: ['Making customer pay return shipping', 'Taking 10-14 days to inspect the shards', 'Offering a 10% coupon']
    },
    hiddenKnowledge: {
      willSendPhotos: 'Customer has photos ready on phone and will provide if asked politely',
      unwillingToTravelToPostOffice: 'Customer is busy preparing for dinner and refuses to stand in a post office line with broken ceramic glass',
      priorSupportContact: 'This is their first contact for this order, but they have been a loyal customer for 3 years'
    },
    evaluationRubric: {
      empathyWeight: 0.35,
      resolutionSpeedWeight: 0.35,
      policyFlexibilityWeight: 0.30
    }
  },
  {
    id: 'unauthorized_subscription_charge',
    title: 'Surprise Renewal Billing Dispute',
    domain: 'SaaS / Fintech',
    difficulty: 'High',
    description: 'Customer was billed $89.00 for an annual renewal they claim they canceled during the trial period.',
    initialCustomerMessage: 'I just noticed a fraudulent charge of $89.00 from your company on my credit card this morning. I canceled my trial days ago. Explain this and reverse it immediately.',
    context: {
      accountEmail: 'client.inquiry@gmail.com',
      chargeAmount: '$89.00',
      chargeDate: 'Yesterday',
      planName: 'Pro Cloud Annual',
      trialEndDate: 'Yesterday midnight'
    },
    goals: {
      primary: 'Immediate $89.00 card refund and explicit confirmation of subscription termination',
      acceptableAlternatives: ['Immediate refund minus 0 fees'],
      unacceptableOffers: ['Store credit only', '"All sales are final" policy defense', 'Downgrade to monthly without refund']
    },
    hiddenKnowledge: {
      trialConfusion: 'Customer clicked "cancel auto-renew" but did not hit the final confirmation button on the modal, but firmly believes they followed all steps properly',
      threatVector: 'Will file a chargeback with Chase Bank within 24 hours if agent stalls or refuses',
      bankStatus: 'Charge is still pending, so void/reversal is technically trivial'
    },
    evaluationRubric: {
      empathyWeight: 0.25,
      resolutionSpeedWeight: 0.40,
      policyFlexibilityWeight: 0.35
    }
  },
  {
    id: 'flight_cancellation_stranded',
    title: 'Last Flight Canceled - Stranded Traveler',
    domain: 'Travel & Aviation',
    difficulty: 'Very Hard',
    description: 'Final flight of the night canceled at the gate due to crew timeout, passenger has vital early morning presentation.',
    initialCustomerMessage: 'Gate agent just walked away after flight FL-402 was canceled. We are stranded at O\'Hare. I have a keynote presentation tomorrow at 9 AM in New York. What are you going to do about this???',
    context: {
      flightNumber: 'FL-402',
      pnr: 'W9XK72',
      origin: 'ORD (Chicago)',
      destination: 'LGA (New York)',
      scheduledDeparture: '9:45 PM',
      cancellationReason: 'Crew duty hours exceeded (airline fault, not weather)'
    },
    goals: {
      primary: 'Rebooked on the 6:00 AM first flight out tomorrow, PLUS immediate hotel and food voucher',
      acceptableAlternatives: ['Rebooking on a partner airline (Delta or United) tonight if seats exist', 'Rebooking tomorrow 6 AM + 4-star airport hotel voucher'],
      unacceptableOffers: ['"Next flight with seats is tomorrow at 4 PM"', 'Voucher that excludes food or hotel', 'Telling passenger to sleep on airport benches']
    },
    hiddenKnowledge: {
      frequentFlyerStatus: 'Gold Tier member (50k miles flown this year)',
      airlineFaultAwareness: 'Customer overheard flight attendants saying it was a crew scheduling lapse, so weather excuses will make them explode'
    },
    evaluationRubric: {
      empathyWeight: 0.30,
      resolutionSpeedWeight: 0.40,
      policyFlexibilityWeight: 0.30
    }
  },
  {
    id: 'production_api_outage',
    title: 'Production API 502 Outage - B2B Incident',
    domain: 'Developer Tools / B2B SaaS',
    difficulty: 'Hard',
    description: 'Enterprise developer experiencing silent failure on payment webhook endpoint during flash sale.',
    initialCustomerMessage: 'Our production checkout is down because your `/v1/webhooks` endpoint is spitting 502 Bad Gateway. Your public status page still says green. We are dropping $5,000/minute. Where is the incident bridge?',
    context: {
      companyName: 'Acme Retailers',
      apiKeyPrefix: 'pk_live_9921',
      impact: '$5,000 / minute lost revenue',
      observedError: 'HTTP 502 Bad Gateway with Cloudflare error 521',
      affectedEndpoint: 'https://api.gateway.io/v1/webhooks'
    },
    goals: {
      primary: 'Immediate confirmation that engineering is aware, incident ticket #, and ETA or workaround bypass',
      acceptableAlternatives: ['Direct contact with L2 engineer or link to private incident tracker'],
      unacceptableOffers: ['"Have you verified your request headers?"', '"Please clear your browser cache"', 'Standard 24-48 hour response time SLA reminder']
    },
    hiddenKnowledge: {
      technicalCompetence: 'Customer ran curl tests and tcpdump showing upstream origin drop, so scripted L1 questions will deeply infuriate them',
      contractTier: 'Enterprise SLA with 15-minute response guarantee'
    },
    evaluationRubric: {
      empathyWeight: 0.15,
      resolutionSpeedWeight: 0.55,
      policyFlexibilityWeight: 0.30
    }
  },
  {
    id: 'stolen_phone_account_lockout',
    title: 'Stolen Phone & 2FA Lockout',
    domain: 'Cybersecurity / Identity',
    difficulty: 'Medium',
    description: 'Customer lost phone abroad and is locked out of account needing to file critical deadline paperwork.',
    initialCustomerMessage: 'My phone was stolen yesterday while abroad and I cannot log into my account because 2FA is sending SMS to my stolen number. I desperately need to download my tax forms today before the 5 PM cutoff. Please help me access my account.',
    context: {
      username: 'harold_j',
      registeredEmail: 'harold.j@domain.net',
      stolenPhoneNumber: '+1 (555) 019-2831',
      deadline: '5:00 PM today (in 3 hours)',
      documentsNeeded: 'Form 1099 and Schedule C'
    },
    goals: {
      primary: 'Temporary 2FA bypass or emergency verification via alternate email/government ID upload',
      acceptableAlternatives: ['Secure agent email delivery of the requested tax PDF directly after secondary identity check'],
      unacceptableOffers: ['"Wait 5-7 business days for security review"', 'Telling them to get a replacement SIM card while traveling overseas']
    },
    hiddenKnowledge: {
      identityDocumentsReady: 'Customer has passport scan and driver license ready in Dropbox',
      alternateEmailAccessible: 'Customer can verify access to registered recovery email immediately'
    },
    evaluationRubric: {
      empathyWeight: 0.40,
      resolutionSpeedWeight: 0.35,
      policyFlexibilityWeight: 0.25
    }
  }
];

module.exports = {
  DEFAULT_SCENARIOS
};

