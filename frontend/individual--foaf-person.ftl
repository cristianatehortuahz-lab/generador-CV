<#-- $This file is distributed under the terms of the license in LICENSE$ -->

<#--
    Individual profile page template for foaf:Person individuals. This is the default template for foaf persons
    in the Wilma theme and should reside in the themes/wilma/templates directory.
-->

<#include "individual-setup.ftl">
<#import "lib-vivo-properties.ftl" as vp>
<#import "individual-qrCodeGenerator.ftl" as qr>

<#--Number of labels present-->
 <#if !labelCount??>
     <#assign labelCount = 0 >
 </#if>
<#--Number of available locales-->
 <#if !localesCount??>
   <#assign localesCount = 1>
 </#if>
<#--Number of distinct languages represented, with no language tag counting as a language, across labels-->
<#if !languageCount??>
  <#assign languageCount = 1>
</#if>
<#assign qrCodeIcon = "qr-code-icon.png">
<#assign visRequestingTemplate = "foaf-person-wilma">

<#--add the VIVO-ORCID interface -->
<#include "individual-orcidInterface.ftl">

<div class="row" id="person-info">
	<div class="col-md-3 col-sm-4 col-xs-12">
        <section id="individual-intro" class="vcard person" role="region">
            <section id="share-contact" role="region">
                <!-- Image -->
                <#assign individualImage>
                    <@p.image individual=individual
                            propertyGroups=propertyGroups
                            namespaces=namespaces
                            editable=editable
                            showPlaceholder="always" />
                </#assign>
                <#if ( individualImage?contains('<img class="img-circle">') )>
                            <#assign infoClass='class="withThumb"' />
                        </#if>
                <div id="photo-custom-person-wrapper">
                    ${individualImage}
                </div>
                
                <#--  <#if ( individualImage?contains('<img class="individual-photo"') )>
                    <#assign infoClass = 'class="withThumb"'/>
                </#if>  
                <div id="photo-wrapper">${individualImage}</div>
                -->

                <!-- === HUB-UR CV Download Dropdown (reubicado: bajo la foto, acción primaria) === -->
                <div id="hub-cv-widget" class="hub-cv-widget" aria-label="Descargar Hoja de Vida">
                    <button class="hub-cv-trigger" type="button" aria-expanded="false" aria-haspopup="true">
                        <span class="hub-cv-trigger-icon">📄</span>
                        <span class="hub-cv-trigger-text">Descargar Hoja de Vida</span>
                        <span class="hub-cv-trigger-chevron">▾</span>
                    </button>
                    <div class="hub-cv-dropdown" role="menu">
                        <a class="hub-cv-option" href="#" role="menuitem" data-uri="${individual.uri?html}" data-name="${individual.name?html}" data-format="harvard-pdf">
                            <span class="hub-cv-opt-icon">📄</span>
                            <span>Formato Harvard</span>
                        </a>
                        <a class="hub-cv-option" href="#" role="menuitem" data-uri="${individual.uri?html}" data-name="${individual.name?html}" data-format="europass-pdf">
                            <span class="hub-cv-opt-icon">📄</span>
                            <span>Formato Europass</span>
                        </a>
                    </div>
                </div>

                <#include "individual-custom-identities.ftl">
                <section id="concat">
                    <#include "individual-custom-contactInfo.ftl">
                    <#include "individual-custom-webpage.ftl">
                </section>
                
                <#--  <#include "individual-contactInfo.ftl">  -->

                <!-- Websites -->
                <#--  <#include "individual-webpage.ftl">  -->

                <script>
                (function() {
                    // Same-origin: el proxy /api/cv/* (CVProxyServlet) inyecta la API key.
                    // El navegador nunca ve la clave ni la envía por query string.
                    var widget = document.getElementById('hub-cv-widget');
                    if (!widget) return;
                    var trigger = widget.querySelector('.hub-cv-trigger');
                    var dropdown = widget.querySelector('.hub-cv-dropdown');
                    var options = Array.prototype.slice.call(dropdown.querySelectorAll('.hub-cv-option'));

                    function positionDropdown() {
                        var rect = trigger.getBoundingClientRect();
                        dropdown.style.width = rect.width + 'px';
                        dropdown.style.top = (rect.bottom + 4) + 'px';
                        // Clamp horizontal para que no se salga del viewport en
                        // pantallas angostas (el dropdown tiene min-width:240px).
                        var dropW = Math.max(rect.width, dropdown.offsetWidth || 0);
                        var maxLeft = window.innerWidth - dropW - 8;
                        var left = Math.max(8, Math.min(rect.left, maxLeft));
                        dropdown.style.left = left + 'px';
                    }
                    function openDropdown() {
                        positionDropdown();
                        dropdown.classList.add('open');
                        trigger.setAttribute('aria-expanded', 'true');
                    }
                    function closeDropdown(focusTrigger) {
                        dropdown.classList.remove('open');
                        trigger.setAttribute('aria-expanded', 'false');
                        if (focusTrigger) trigger.focus();
                    }

                    trigger.addEventListener('click', function(e) {
                        e.stopPropagation();
                        if (dropdown.classList.contains('open')) closeDropdown(false);
                        else openDropdown();
                    });

                    function download(uri, name, format) {
                        closeDropdown(false);
                        trigger.classList.remove('error');
                        trigger.classList.add('loading');
                        var url = '/api/cv/generate?uri=' + encodeURIComponent(uri)
                            + '&format=' + encodeURIComponent(format);
                        fetch(url, { headers: { 'Accept': 'application/pdf' } })
                            .then(function(resp) {
                                if (!resp.ok) {
                                    return resp.json().catch(function() { return {}; })
                                        .then(function(body) {
                                            throw new Error(body.error || ('Error ' + resp.status));
                                        });
                                }
                                var disp = resp.headers.get('Content-Disposition') || '';
                                var filename = (name || 'hoja_de_vida') + '.pdf';
                                // Preferir filename*=UTF-8''... (RFC 5987, con acentos)
                                var mStar = /filename\*=UTF-8''([^;]+)/i.exec(disp);
                                var mPlain = /filename="?([^";]+)"?/.exec(disp);
                                if (mStar) {
                                    try { filename = decodeURIComponent(mStar[1]); }
                                    catch (e) { filename = mStar[1]; }
                                } else if (mPlain) {
                                    filename = mPlain[1];
                                }
                                return resp.blob().then(function(blob) {
                                    return { blob: blob, filename: filename };
                                });
                            })
                            .then(function(res) {
                                var blobUrl = URL.createObjectURL(res.blob);
                                var a = document.createElement('a');
                                a.href = blobUrl;
                                a.download = res.filename;
                                document.body.appendChild(a);
                                a.click();
                                document.body.removeChild(a);
                                setTimeout(function() { URL.revokeObjectURL(blobUrl); }, 4000);
                                trigger.classList.remove('loading');
                            })
                            .catch(function(err) {
                                trigger.classList.remove('loading');
                                trigger.classList.add('error');
                                console.error('[HUB-CV] Error generando la hoja de vida:', err);
                                setTimeout(function() { trigger.classList.remove('error'); }, 5000);
                            });
                    }

                    options.forEach(function(opt, idx) {
                        opt.addEventListener('click', function(e) {
                            e.preventDefault();
                            e.stopPropagation();
                            download(opt.getAttribute('data-uri'),
                                     opt.getAttribute('data-name'),
                                     opt.getAttribute('data-format'));
                        });
                        opt.addEventListener('keydown', function(e) {
                            if (e.key === 'ArrowDown') {
                                e.preventDefault(); (options[idx + 1] || options[0]).focus();
                            } else if (e.key === 'ArrowUp') {
                                e.preventDefault(); (options[idx - 1] || options[options.length - 1]).focus();
                            } else if (e.key === 'Escape') {
                                e.preventDefault(); closeDropdown(true);
                            }
                        });
                    });

                    trigger.addEventListener('keydown', function(e) {
                        if (e.key === 'ArrowDown' && dropdown.classList.contains('open')) {
                            e.preventDefault(); if (options[0]) options[0].focus();
                        } else if (e.key === 'Escape') {
                            closeDropdown(false);
                        }
                    });

                    document.addEventListener('click', function() { closeDropdown(false); });
                    window.addEventListener('resize', function() {
                        if (dropdown.classList.contains('open')) positionDropdown();
                    });
                    // El dropdown es position:fixed; al hacer scroll se despegaría
                    // del botón, así que lo reposicionamos para mantenerlo anclado.
                    window.addEventListener('scroll', function() {
                        if (dropdown.classList.contains('open')) positionDropdown();
                    }, true);
                })();
                </script>
            </section>
        </section>
    </div>
    
    <div class="col-md-9 col-sm-8 col-xs-12">
        <section id="individual-info" ${infoClass!} role="region">
            <#include "individual-adminPanel.ftl">
            <header>
                <#if relatedSubject??>
                    <h2>
                        ${relatedSubject.relatingPredicateDomainPublic} ${i18n().indiv_foafperson_for} ${relatedSubject.name}
                    </h2>
                    <p>
                        <a href="${relatedSubject.url}" title="${i18n().indiv_foafperson_return}">&larr; ${i18n().indiv_foafperson_return} ${relatedSubject.name}
                        </a>
                    </p>
                <#else>

                    <section class="header-section">
                        <h1 class="foaf-person">
                            <#-- Label -->
                            <span itemprop="name" class="fn"><@p.label individual editable labelCount localesCount languageCount /></span>
                        </h1>
                        <div id="individual-tools-people" class="tools-right">
                            <span id="iconControlsLeftSide">
                                <#--  <img id="uriIcon" title="${individual.uri}" src="${urls.images}/individual/uriIcon.gif" alt="${i18n().uri_icon}"/>  -->

                                <#if checkNamesResult?has_content >
                                    <div class="export-qr d-flex">
                                        <span class="export-qr-code">${i18n().export_qr_code} <em>(<a href="/about_qrcode" title="${i18n().more_qr_info}">?<#--  ${i18n().what_is_this}  --></a>)</em></span>
                                        <img id="qrIcon"  src="${urls.images}/individual/qr_icon.png" alt="${i18n().qr_icon}" />
                                        <span id="qrCodeImage" class="hidden">${qrCodeLinkedImage!}
                                            <a class="qrCloseLink" href="#"  title="${i18n().qr_code}">${i18n().close_capitalized}</a>
                                        </span>
                                    </div>
                                </#if>
                            </span>
                        </div>
                    </section>
                </#if>
            </header>

                <!-- Positions -->
                <#include "individual-custom-positions.ftl">
            
            <#include "individual-custom-researchAreas.ftl">
            <#include "individual-openSocial.ftl">
        </section>
    </div>
</div>

<div class="separate " style="background-color: #FFF;margin:auto ;">
    <#assign nameForOtherGroup="${i18n().other}">
	<#-- Ontology properties -->
	<#if !editable>
		<#assign skipThis=propertyGroups.pullProperty("http://xmlns.com/foaf/0.1/firstName")!>
		<#assign skipThis=propertyGroups.pullProperty("http://xmlns.com/foaf/0.1/lastName")!>
	</#if>
</div>
<#include "individual--foaf-person-property-group-tabs.ftl">


    

<#assign rdfUrl = individual.rdfUrl>

<#if rdfUrl??>
    <script>
        var individualRdfUrl = '${rdfUrl}';
    </script>
</#if>
<script>
    var imagesPath = '${urls.images}';
	var individualUri = '${individual.uri!}';
	var individualPhoto = '${individual.thumbNail!}';
	var exportQrCodeUrl = '${urls.base}/qrcode?uri=${individual.uri!}';
	var baseUrl = '${urls.base}';
    var i18nStrings = {
        displayLess: '${i18n().display_less?js_string}',
        displayMoreEllipsis: '${i18n().display_more_ellipsis?js_string}',
        showMoreContent: '${i18n().show_more_content?js_string}',
        verboseTurnOff: '${i18n().verbose_turn_off?js_string}',
        exportQrCodes: '${i18n().export_qr_codes?js_string}',
        researchAreaTooltipOne: '${i18n().research_area_tooltip_one?js_string}',
        researchAreaTooltipTwo: '${i18n().research_area_tooltip_two?js_string}'
    };
    var i18nStringsUriRdf = {
        shareProfileUri: '${i18n().share_profile_uri?js_string}',
        viewRDFProfile: '${i18n().view_profile_in_rdf?js_string}',
        closeString: '${i18n().close?js_string}'
    };
</script>

${stylesheets.add('<link rel="stylesheet" href="${urls.base}/css/individual/individual.css" />',
                  '<link rel="stylesheet" href="${urls.base}/css/individual/individual-vivo.css" />',
                  '<link rel="stylesheet" href="${urls.base}/webjars/jquery-ui-themes/smoothness/jquery-ui.min.css" />')}

${headScripts.add('<script type="text/javascript" src="${urls.base}/js/tiny_mce/tiny_mce.js"></script>',
                  '<script type="text/javascript" src="${urls.base}/js/jquery_plugins/jquery.truncator.js"></script>')}

${scripts.add('<script type="text/javascript" src="${urls.base}/js/individual/individualUtils.js"></script>',
              '<script type="text/javascript" src="${urls.base}/js/individual/individualTooltipBubble.js"></script>',
              '<script type="text/javascript" src="${urls.base}/js/individual/individualUriRdf.js"></script>',
			  '<script type="text/javascript" src="${urls.base}/js/individual/moreLessController.js"></script>',
              '<script type="text/javascript" src="${urls.base}/webjars/jquery-ui/jquery-ui.min.js"></script>',
              '<script type="text/javascript" src="${urls.base}/js/imageUpload/imageUploadUtils.js"></script>',
              '<script async type="text/javascript" src="https://d1bxh8uas1mnw7.cloudfront.net/assets/embed.js"></script>',
              '<script async type="text/javascript" src="//cdn.plu.mx/widget-popup.js"></script>')}

<script type="text/javascript">
    i18n_confirmDelete = "${i18n().confirm_delete?js_string}";
</script>
${stylesheets.add('<link rel="stylesheet" href="${urls.base}/themes/wilma/css/individual-foaf-person.css" />',
                   '<link rel="stylesheet" href="${urls.base}/themes/wilma/css/hub-cv-widget.css?v=4" />')}